"""Module defining views for the JASMIN services app."""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import functools
import logging
import socket
from datetime import date

import django.contrib.auth
import requests as reqs
from dateutil.relativedelta import relativedelta
from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.http import urlquote
from django.views.decorators.http import require_http_methods

from .forms import (
    DecisionForm,
    GrantReviewForm,
    grant_form_factory,
    message_form_factory,
)
from .models import Access, Category, Grant, Group, Request, RequestState, Role, Service

_log = logging.getLogger(__name__)
