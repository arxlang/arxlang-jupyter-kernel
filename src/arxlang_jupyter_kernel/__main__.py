"""
title: Launch the Arx Jupyter kernel module entrypoint.
"""

from ipykernel.kernelapp import IPKernelApp

from .kernel import ArxKernel


def main() -> None:
    """
    title: Launch the Arx kernel via IPKernelApp.
    """
    IPKernelApp.launch_instance(kernel_class=ArxKernel)


if __name__ == "__main__":
    main()
