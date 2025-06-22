from setuptools import setup
from Cython.Build import cythonize

# This setup script compiles the Cython file 'image_processor.pyx' into a Python extension module.
setup(
    ext_modules = cythonize("image_processor.pyx", compiler_directives={'language_level': "3"})
)