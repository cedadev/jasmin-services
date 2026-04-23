from django.db import models

class AuthStatus(Expression):



class Auth(models.Model):

    role = 
    user =

    created_at =
    created_by = 

    approved_at =
    approved_by = 
    expires_at = 
    approval_comment = 

    revoked_at = 
    revoked_by = 
    revocation_comment =

    internal_comment = 

    # Generated fields
    status = 
    # pending -> revoked
    # pending -> approved -> revoked
    # pending -> approved -> expiring -> expired
    # pending -> approved -> expiring -> renewed




