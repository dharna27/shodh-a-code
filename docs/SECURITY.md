# Security notes

The API and worker containers do not mount the Docker socket. The runner gateway does mount it and thus has effectively host-root-equivalent authority. This is a **development-only** architecture. Do not expose the runner port or use it on a machine with sensitive workloads. The runner authenticates requests with a shared secret, but this does not make Docker socket mounting safe against compromise of the runner service.

Submitted code executes in a separate Docker container with `--network none`, non-root UID, no capabilities, read-only filesystem, process/memory/CPU restrictions, and no Docker socket. The source file is read-only mounted. No credentials or hidden expected outputs are mounted. This is not a substitute for hardened production sandboxing.

Use a dedicated disposable Docker host for untrusted code. The provided implementation is suitable only for locally controlled example programs until the runner is hardened and validated.
