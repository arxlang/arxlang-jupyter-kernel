# arxlang-jupyter-kernel

`arxlang-jupyter-kernel` is a wrapper-style Jupyter kernel for ArxLang. Each
cell is compiled with the Arx CLI, executed as a native binary, and its
stdout/stderr is returned to Jupyter.

This first version does not require any changes inside the Arx compiler
codebase.

## Requirements

- Python 3.10+
- `arx` CLI available on `PATH` (or set `ARX_BIN`)
- Jupyter Notebook/Lab or Quarto with Jupyter support

## Install

```bash
pip install .
```

Register the kernel

```bash
python -m arxlang_jupyter_kernel.install --user
```

Validate installation:

```bash
jupyter kernelspec list
```

You should see an arx kernelspec with display name ArxLang.

## Execution model

Each cell is compiled and run in a temporary build directory. The kernel keeps a
session prelude with all previously successful cells. New cells compile as:
session prelude + current cell. Compilation errors are returned as Jupyter error
messages. Failed compilations do not update session source. Quarto usage Use the
arx kernel id in document front matter:

```yaml
---
title: "Arx Notebook"
jupyter: arx
---
```

## Environment variables

- `ARX_BIN` Default: arx Path/executable for Arx CLI.

- `ARX_COMPILE_ARGS` Default: empty Extra compile args, parsed shell-style.

- `ARX_RUN_ARGS` Default: empty Extra runtime args, parsed shell-style.

- `ARX_KERNEL_KEEP_BUILD` Default: 0 Set to 1 to keep temporary build
  directories for debugging.

- `ARX_KERNEL_SESSION_FILE` Default: unset Optional file path for persisting
  successful session source.

## CLI command assumption and TODO

Current compile command guess is:

```bash
arx build <source> -o <binary> [ARX_COMPILE_ARGS...]
```

Runtime command is:

```bash
<binary> [ARX_RUN_ARGS...]
```

If the final Arx CLI differs, update `src/arxlang_jupyter_kernel/compile_run.py`
in `build_compile_command()`.

## Troubleshooting

- `ArxCompileError` with "No such file or directory: 'arx'" Ensure Arx CLI is
  installed or set `ARX_BIN=/full/path/to/arx`.
- Compiles fail due to CLI mismatch Adjust `build_compile_command()` to the
  finalized Arx CLI syntax.
- Need compiler artifacts for debugging Set `ARX_KERNEL_KEEP_BUILD=1` before
  launching Jupyter.
- Kernel installed but not visible Re-run install and verify
  `jupyter kernelspec list` output.
