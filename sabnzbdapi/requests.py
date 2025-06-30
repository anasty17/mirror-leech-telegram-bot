from httpx import AsyncClient, AsyncHTTPTransport, Timeout
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from .job_functions import JobFunctions
from .exception import APIConnectionError


class SabnzbdClient(JobFunctions):

    LOGGED_IN = False

    def __init__(
        self,
        host: str,
        api_key: str,
        port: str = "8070",
        VERIFY_CERTIFICATE: bool = False,
        RETRIES: int = 10,
        HTTPX_REQUETS_ARGS: dict = None,
    ):
        if HTTPX_REQUETS_ARGS is None:
            HTTPX_REQUETS_ARGS = {}
        self._base_url = f"{host.rstrip('/')}:{port}"
        self._default_params = {"apikey": api_key, "output": "json"}
        self._VERIFY_CERTIFICATE = VERIFY_CERTIFICATE
        self._RETRIES = RETRIES
        self._HTTPX_REQUETS_ARGS = HTTPX_REQUETS_ARGS
        self._http_session = None
        if not self._VERIFY_CERTIFICATE:
            disable_warnings(InsecureRequestWarning)
        super().__init__()

    def _session(self):
        if self._http_session is not None:
            return self._http_session

        transport = AsyncHTTPTransport(
            retries=self._RETRIES, verify=self._VERIFY_CERTIFICATE
        )

        self._http_session = AsyncClient(
            base_url=self._base_url,
            transport=transport,
            timeout=Timeout(connect=60, read=60, write=60, pool=None),
            follow_redirects=True,
            verify=self._VERIFY_CERTIFICATE,
            **self._HTTPX_REQUETS_ARGS,
        )

        return self._http_session

    async def call(
        self,
        params: dict = None,
        requests_args: dict = None,
        **kwargs,
    ):
        if requests_args is None:
            requests_args = {}
        session = self._session()
        params |= kwargs
        res = await session.get(
            url="/sabnzbd/api",
            params={**self._default_params, **params},
            **requests_args,
        )
        response = res.json()
        if response is None:
            raise APIConnectionError("Failed to connect to API!")
        return response

    async def close(self):
        if self._http_session is not None:
            await self._http_session.aclose()
            self._http_session = None
