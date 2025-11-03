# Grant Lifecycle

## Overview

Grants represent approved access to services and roles within the JASMIN system. Each grant has a lifecycle that includes creation, potential expiry or revocation, and possible reinstatement under certain conditions.

## Grant States

A grant can be in one of the following states:

- **ACTIVE**: Grant is neither revoked nor expired
- **EXPIRING**: Grant expires within the next 2 months
- **EXPIRED**: Grant expiry date has passed
- **REVOKED**: Grant has been explicitly revoked

## Grant Chain Structure

Grants form chains through the `previous_grant` relationship. When a grant is superseded (e.g., renewed or replaced), a new grant is created that points to the old one via `previous_grant`. The "active" grant for any access is the one at the head of the chain (without a `next_grant` relationship).

## Account Suspension

When a user account is suspended (account `is_active` set to `False`):

1. All active grants are revoked with `user_reason` set to "Account was suspended"
2. All pending requests are rejected with the same reason
3. Access to services is disabled via the behavior system

## Account Reactivation

When a user account is reactivated (account `is_active` set to `True`), the system attempts to reinstate previously suspended grants:

### Eligibility Criteria

The system only considers grants that:
- Were revoked with `user_reason` of "Account was suspended"
- Belong to roles in services that are not disabled
- Are "active" grants (at the head of their grant chain)

### Reinstatement Logic

For each eligible grant:

1. **If the grant has not expired** (`expires > today`):
   - The grant is fully reinstated
   - `revoked` flag is set to `False`
   - `user_reason` is cleared
   - Original expiry date is preserved

2. **If the grant expired within the last two years** (`expires >= today - 730 days`):
   - A new grant is created with a 30-day expiry
   - The new grant links to the old grant via `previous_grant`
   - Original `granted_by` value is preserved
   - This gives the user temporary access to renew properly

3. **If the grant expired more than two years ago**:
   - The grant is **not** reinstated
   - No new grant is created
   - The user must request access again through the normal request process

### Rationale for Two-Year Limit

The two-year limit prevents automatic reinstatement of very old grants that:
- May have belonged to projects that no longer exist
- Could have had requirements or policies that have changed significantly
- Might represent access the user no longer needs
- Should be re-evaluated through the normal request and approval process

## Request Reinstatement

Pending requests that were rejected due to account suspension are also reinstated when the account is reactivated, regardless of when they were rejected.

## Related Code

- Grant model: `jasmin_services/models/grant.py`
- Suspension/reactivation handlers: `jasmin_services/notifications.py` (functions `account_suspended` and `account_reactivated`)
- Access synchronization: `jasmin_services/notifications.py:199` (function `grant_sync_access`)
