"""Module entrypoint for launching the Arx Jupyter kernel."""

from ipykernel.kernelapp import IPKernelApp

from .kernel import ArxKernel


def main() -> None:
    """Launch the Arx kernel via IPKernelApp."""
    IPKernelApp.launch_instance(kernel_class=ArxKernel)


if __name__ == "__main__":
    main()
