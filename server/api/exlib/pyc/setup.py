from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize("image_processor.pyx", compiler_directives={'language_level': "3"})
)