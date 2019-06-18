#!/usr/bin/env python3

import os, re
from setuptools import setup, find_packages


here = os.path.abspath(os.path.dirname(__file__))


with open(os.path.join(here, 'README.md')) as f:
    README = f.read()

if __name__ == "__main__":
    setup(
        name = 'jasmin-services',
        setup_requires = ['setuptools_scm'],
        use_scm_version = True,
        description = 'Django application for managing services, roles and access',
        long_description = README,
        classifiers = [
            "Programming Language :: Python",
            "Framework :: Django",
            "Topic :: Internet :: WWW/HTTP",
            "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
        author = 'Matt Pryor',
        author_email = 'matt.pryor@stfc.ac.uk',
        url = 'https://github.com/cedadev/jasmin-services',
        keywords = 'web django jasmin services role based access control rbac',
        packages = find_packages(),
        include_package_data = True,
        zip_safe = False,
        install_requires = [
            'django',
            'jasmin-ldap-django',
            'jasmin-metadata',
            'jasmin-notifications',
            'django-bootstrap3',
            'django-markdown-deux',
            'python-dateutil',
            'django-polymorphic',
            'requests',
        ],
    )
