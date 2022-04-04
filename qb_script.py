import sys, os, subprocess, argparse

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--torrent_name")
parser.add_argument("-l", "--category", nargs="?", const="")
parser.add_argument("-f", "--content_path")
parser.add_argument("-r", "--root_path", nargs="?", const="")
parser.add_argument("-d", "--save_path", nargs="?", const="")
parser.add_argument("-c", "--number_of_files", nargs="?", const="", type=int)
parser.add_argument("-z", "--torrent_size", nargs="?", const="", type=int)

args = parser.parse_args()

print("Torrent Name: %s" % args.torrent_name)

name = os.path.basename(args.root_path)
proc = subprocess.Popen(
    [
        "gclone",
        "copy",
        args.root_path,
        "ld:/[ Downloads ]/[ Temp ]/%s" % name,
        "-v",
    ],
    stdout=subprocess.PIPE,
)
for c in iter(lambda: proc.stdout.read(1), b""):
    sys.stdout.buffer.write(c)

proc = subprocess.Popen(
    [
        "gclone",
        "move",
        "ld:/[ Downloads ]/[ Temp ]/%s" % name,
        "ld:/[ Downloads ]/%s" % name,
        "-v",
    ],
    stdout=subprocess.PIPE,
)
for c in iter(lambda: proc.stdout.read(1), b""):
    sys.stdout.buffer.write(c)
    
print("Copy of %s complete!" % args.torrent_name)
