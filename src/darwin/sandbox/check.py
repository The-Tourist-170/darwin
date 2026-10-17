"""Sandbox check CLI: verify a backend end to end without the agent.

    python -m darwin.sandbox.check                 # detected backends and the image allowlist
    python -m darwin.sandbox.check python          # run a snippet in python:3.12-slim
    python -m darwin.sandbox.check rust 'fn main(){println!("ok")}'
    python -m darwin.sandbox.check lima            # only if you opted into the VM
"""

import argparse

from darwin import sandbox
from darwin.sandbox import docker, lima
from darwin.tools.sandbox import RUNNERS, run_code

SNIPPETS = {
    "python": "print(6 * 7)",
    "node": "console.log(6 * 7)",
    "bash": "echo hello from the sandbox",
    "go": 'package main\nimport "fmt"\nfunc main() { fmt.Println(6 * 7) }',
    "rust": 'fn main() { println!("{}", 6 * 7) }',
    "cpp": '#include <iostream>\nint main() { std::cout << 6 * 7 << std::endl; }',
    "java": 'public class Main { public static void main(String[] a) { System.out.println(6 * 7); } }',
    "bun": "console.log(6 * 7)",
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="darwin.sandbox.check", description="Test an execution backend")
    parser.add_argument("language", nargs="?", help="Language to run in the sandbox")
    parser.add_argument("command", nargs="?", help="Command to run (defaults to a hello-world snippet)")
    parsed = parser.parse_args()

    print(f"docker available: {docker.available()}")
    print(f"lima available:   {lima.available()}")
    for name, image in docker.IMAGES.items():
        print(f"  {name:8} {image}")

    if not parsed.language:
        return

    if parsed.language == "lima":
        print(sandbox.run("bash", "uname -a", 60, backend="lima"))
        return

    language = parsed.language
    if parsed.command:
        print(sandbox.run(language, parsed.command, 120))
        return

    if language not in RUNNERS:
        print(f"unknown language '{language}'; choose one of: {', '.join(RUNNERS)}, or pass a command")
        return
    print(run_code.invoke({"language": language, "code": SNIPPETS[language], "timeout": 300}))


if __name__ == "__main__":
    main()