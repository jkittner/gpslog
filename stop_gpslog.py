import subprocess


def main():
    pid_cmd = ['pgrep', '-f', '.gpslog']
    pid = subprocess.check_output(pid_cmd).decode().split('\n')[0]
    kill_cmd = ['kill', '-s', 'SIGTERM', pid]
    subprocess.run(kill_cmd)


if __name__ == '__main__':
    exit(main())
