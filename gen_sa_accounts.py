from argparse import ArgumentParser
from base64 import b64decode
from errno import EEXIST
from glob import glob
from json import loads
from os import mkdir, path as ospath
from pickle import dump, load
from random import choice
from sys import exit
from time import sleep

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/iam",
]
project_create_ops = []
current_key_dump = []
sleep_time = 30
CHARS = "-abcdefghijklmnopqrstuvwxyz1234567890"


def _create_accounts(service, project, count):
    batch = service.new_batch_http_request(callback=_def_batch_resp)
    for _ in range(count):
        aid = _generate_id("mfc-")
        batch.add(
            service.projects()
            .serviceAccounts()
            .create(
                name=f"projects/{project}",
                body={
                    "accountId": aid,
                    "serviceAccount": {"displayName": aid},
                },
            )
        )
    try:
        batch.execute()
    except HttpError as e:
        print("Error creating accounts:", e)


def _create_remaining_accounts(iam, project):
    print(f"Creating accounts in {project}")
    sa_count = len(_list_sas(iam, project))
    while sa_count != 100:
        _create_accounts(iam, project, 100 - sa_count)
        sa_count = len(_list_sas(iam, project))


def _generate_id(prefix="saf-"):
    return prefix + "".join(choice(CHARS) for _ in range(25)) + choice(CHARS[1:])


def _get_projects(service):
    try:
        return [i["projectId"] for i in service.projects().list().execute()["projects"]]
    except HttpError as e:
        print("Error fetching projects:", e)
        return []


def _def_batch_resp(id, resp, exception):
    if exception is not None:
        if str(exception).startswith("<HttpError 429"):
            sleep(sleep_time / 100)
        else:
            print("Batch error:", exception)


def _pc_resp(id, resp, exception):
    global project_create_ops
    if exception is not None:
        print("Project creation error:", exception)
    else:
        for i in resp.values():
            project_create_ops.append(i)


def _create_projects(cloud, count):
    global project_create_ops
    batch = cloud.new_batch_http_request(callback=_pc_resp)
    new_projs = []
    for _ in range(count):
        new_proj = _generate_id()
        new_projs.append(new_proj)
        batch.add(cloud.projects().create(body={"project_id": new_proj}))
    try:
        batch.execute()
    except HttpError as e:
        print("Error creating projects:", e)
        return []

    for op in project_create_ops:
        while True:
            try:
                resp = cloud.operations().get(name=op).execute()
                if resp.get("done"):
                    break
            except HttpError as e:
                print("Error fetching operation status:", e)
                break
            sleep(3)
    return new_projs


def _enable_services(service, projects, ste):
    batch = service.new_batch_http_request(callback=_def_batch_resp)
    for project in projects:
        for s in ste:
            batch.add(
                service.services().enable(name=f"projects/{project}/services/{s}")
            )
    try:
        batch.execute()
    except HttpError as e:
        print("Error enabling services:", e)


def _list_sas(iam, project):
    try:
        resp = (
            iam.projects()
            .serviceAccounts()
            .list(name=f"projects/{project}", pageSize=100)
            .execute()
        )
        return resp.get("accounts", [])
    except HttpError as e:
        print("Error listing service accounts:", e)
        return []


def _batch_keys_resp(id, resp, exception):
    global current_key_dump
    if exception is not None:
        current_key_dump = None
        sleep(sleep_time / 100)
    elif current_key_dump is None:
        sleep(sleep_time / 100)
    else:
        try:
            key_name = resp["name"][resp["name"].rfind("/") :]
            key_data = b64decode(resp["privateKeyData"]).decode("utf-8")
            current_key_dump.append((key_name, key_data))
        except Exception as e:
            print("Error processing key response:", e)


def _create_sa_keys(iam, projects, path_dir):
    global current_key_dump
    for project in projects:
        current_key_dump = []
        print(f"Downloading keys from {project}")
        while current_key_dump is None or len(current_key_dump) != 100:
            batch = iam.new_batch_http_request(callback=_batch_keys_resp)
            total_sas = _list_sas(iam, project)
            for sa in total_sas:
                batch.add(
                    iam.projects()
                    .serviceAccounts()
                    .keys()
                    .create(
                        name=f"projects/{project}/serviceAccounts/{sa['uniqueId']}",
                        body={
                            "privateKeyType": "TYPE_GOOGLE_CREDENTIALS_FILE",
                            "keyAlgorithm": "KEY_ALG_RSA_2048",
                        },
                    )
                )
            try:
                batch.execute()
            except HttpError as e:
                print("Error creating SA keys:", e)
                current_key_dump = None

            if current_key_dump is None:
                print(f"Redownloading keys from {project}")
                current_key_dump = []
            else:
                for index, key in enumerate(current_key_dump):
                    try:
                        with open(f"{path_dir}/{index}.json", "w+") as f:
                            f.write(key[1])
                    except IOError as e:
                        print(f"Error writing key file {index}.json:", e)


def _delete_sas(iam, project):
    sas = _list_sas(iam, project)
    batch = iam.new_batch_http_request(callback=_def_batch_resp)
    for account in sas:
        batch.add(iam.projects().serviceAccounts().delete(name=account["name"]))
    try:
        batch.execute()
    except HttpError as e:
        print("Error deleting service accounts:", e)


def serviceaccountfactory(
    credentials="credentials.json",
    token="token_sa.pickle",
    path=None,
    list_projects=False,
    list_sas=None,
    create_projects=None,
    max_projects=12,
    enable_services=None,
    services=["iam", "drive"],
    create_sas=None,
    delete_sas=None,
    download_keys=None,
):
    selected_projects = []
    try:
        proj_id = loads(open(credentials, "r").read())["installed"]["project_id"]
    except Exception as e:
        exit("Error reading credentials file: " + str(e))

    creds = None
    if path and not path:
        path = "accounts"
    if path and not path.endswith("/"):
        path = path.rstrip("/")

    if path and not path == "accounts":
        try:
            mkdir(path)
        except OSError as e:
            if e.errno != EEXIST:
                print("Error creating output directory:", e)
                exit(1)

    if ospath.exists(token):
        try:
            with open(token, "rb") as t:
                creds = load(t)
        except Exception as e:
            print("Error loading token file:", e)
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials, SCOPES)
                creds = flow.run_local_server(port=0, open_browser=False)
            with open(token, "wb") as t:
                dump(creds, t)
        except Exception as e:
            exit("Error obtaining credentials: " + str(e))

    try:
        cloud = build("cloudresourcemanager", "v1", credentials=creds)
        iam = build("iam", "v1", credentials=creds)
        serviceusage = build("serviceusage", "v1", credentials=creds)
    except Exception as e:
        exit("Error building service clients: " + str(e))

    projs = None
    while projs is None:
        try:
            projs = _get_projects(cloud)
        except HttpError:
            try:
                serviceusage.services().enable(
                    name=f"projects/{proj_id}/services/cloudresourcemanager.googleapis.com"
                ).execute()
            except HttpError as ee:
                print("Error enabling cloudresourcemanager:", ee)
                input("Press Enter to retry.")
    if list_projects:
        return _get_projects(cloud)
    if list_sas:
        return _list_sas(iam, list_sas)
    if create_projects:
        print(f"Creating projects: {create_projects}")
        if create_projects > 0:
            current_count = len(_get_projects(cloud))
            if current_count + create_projects <= max_projects:
                print("Creating %d projects" % create_projects)
                nprjs = _create_projects(cloud, create_projects)
                selected_projects = nprjs
            else:
                exit(
                    "Cannot create %d new project(s).\n"
                    "Please reduce the value or delete existing projects.\n"
                    "Max projects allowed: %d, already in use: %d"
                    % (create_projects, max_projects, current_count)
                )
        else:
            print("Overwriting all service accounts in existing projects.")
            input("Press Enter to continue...")

    if enable_services:
        target = [enable_services]
        if enable_services == "~":
            target = selected_projects
        elif enable_services == "*":
            target = _get_projects(cloud)
        service_list = [f"{s}.googleapis.com" for s in services]
        print("Enabling services")
        _enable_services(serviceusage, target, service_list)
    if create_sas:
        target = [create_sas]
        if create_sas == "~":
            target = selected_projects
        elif create_sas == "*":
            target = _get_projects(cloud)
        for proj in target:
            _create_remaining_accounts(iam, proj)
    if download_keys:
        target = [download_keys]
        if download_keys == "~":
            target = selected_projects
        elif download_keys == "*":
            target = _get_projects(cloud)
        _create_sa_keys(iam, target, path)
    if delete_sas:
        target = [delete_sas]
        if delete_sas == "~":
            target = selected_projects
        elif delete_sas == "*":
            target = _get_projects(cloud)
        for proj in target:
            print(f"Deleting service accounts in {proj}")
            _delete_sas(iam, proj)


if __name__ == "__main__":
    parse = ArgumentParser(description="A tool to create Google service accounts.")
    parse.add_argument(
        "--path",
        "-p",
        default="accounts",
        help="Specify an alternate directory to output the credential files.",
    )
    parse.add_argument("--token", default="token_sa.pickle", help="Token file path.")
    parse.add_argument(
        "--credentials",
        default="credentials.json",
        help="Credentials file path.",
    )
    parse.add_argument(
        "--list-projects",
        default=False,
        action="store_true",
        help="List projects viewable by the user.",
    )
    parse.add_argument(
        "--list-sas", default=False, help="List service accounts in a project."
    )
    parse.add_argument(
        "--create-projects", type=int, default=None, help="Creates up to N projects."
    )
    parse.add_argument(
        "--max-projects",
        type=int,
        default=12,
        help="Max projects allowed. Default: 12",
    )
    parse.add_argument(
        "--enable-services",
        default=None,
        help="Enables services on the project. Default: IAM and Drive",
    )
    parse.add_argument(
        "--services",
        nargs="+",
        default=["iam", "drive"],
        help="Specify a different set of services to enable.",
    )
    parse.add_argument(
        "--create-sas", default=None, help="Create service accounts in a project."
    )
    parse.add_argument(
        "--delete-sas", default=None, help="Delete service accounts in a project."
    )
    parse.add_argument(
        "--download-keys",
        default=None,
        help="Download keys for service accounts in a project.",
    )
    parse.add_argument(
        "--quick-setup",
        default=None,
        type=int,
        help="Create projects, enable services, create SAs and download keys.",
    )
    parse.add_argument(
        "--new-only",
        default=False,
        action="store_true",
        help="Do not use existing projects.",
    )
    args = parse.parse_args()

    if not ospath.exists(args.credentials):
        options = glob("*.json")
        print(
            "No credentials found at %s. Please enable the Drive API and save the JSON as %s."
            % (args.credentials, args.credentials)
        )
        if not options:
            exit("No available credential files found.")
        else:
            print("Select a credentials file:")
            for idx, opt in enumerate(options):
                print(f"  {idx + 1}) {opt}")
            while True:
                inp = input("> ")
                try:
                    choice_idx = int(inp) - 1
                    if 0 <= choice_idx < len(options):
                        args.credentials = options[choice_idx]
                        break
                except ValueError:
                    if inp in options:
                        args.credentials = inp
                        break
            print(
                f"Use --credentials {args.credentials} next time to use this credentials file."
            )
    if args.quick_setup:
        opt = "~" if args.new_only else "*"
        args.services = ["iam", "drive"]
        args.create_projects = args.quick_setup
        args.enable_services = opt
        args.create_sas = opt
        args.download_keys = opt
    resp = serviceaccountfactory(
        path=args.path,
        token=args.token,
        credentials=args.credentials,
        list_projects=args.list_projects,
        list_sas=args.list_sas,
        create_projects=args.create_projects,
        max_projects=args.max_projects,
        create_sas=args.create_sas,
        delete_sas=args.delete_sas,
        enable_services=args.enable_services,
        services=args.services,
        download_keys=args.download_keys,
    )
    if resp is not None:
        if args.list_projects:
            if resp:
                print("Projects (%d):" % len(resp))
                for proj in resp:
                    print(f"  {proj}")
            else:
                print("No projects found.")
        elif args.list_sas:
            if resp:
                print("Service accounts in %s (%d):" % (args.list_sas, len(resp)))
                for sa in resp:
                    print(f"  {sa['email']} ({sa['uniqueId']})")
            else:
                print("No service accounts found.")
