"""Fail-closed gate for the user's zero-paid-charge constraint."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re


def deployment_policy(plan, account, temporary_metered=False, now=None):
    if not isinstance(account, str) or not re.fullmatch(r'[0-9]{12}', account):
        raise ValueError('Authenticated AWS account identity is invalid')
    if temporary_metered is True:
        return 'TEMPORARY_METERED_DEMO'
    if temporary_metered is not False:
        raise ValueError('Metered demo approval must be explicit')
    check_free_plan(plan, account, now)
    return 'FREE_ACTIVE'


def check_free_plan(plan, account, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        if plan['accountId'] != account or plan['accountPlanType'] != 'FREE' or plan['accountPlanStatus'] != 'ACTIVE':
            raise ValueError('Only an ACTIVE FREE account plan in the authenticated account is allowed')
        expiry = plan['accountPlanExpirationDate']
        expiry = datetime.fromtimestamp(expiry, timezone.utc) if isinstance(expiry, (int, float)) else datetime.fromisoformat(expiry.replace('Z', '+00:00'))
        if expiry.tzinfo is None or expiry <= now + timedelta(minutes=30):
            raise ValueError('Free account plan is expired or too close to expiry')
        credits = plan['accountPlanRemainingCredits']
        amount = Decimal(str(credits['amount']))
        if not amount.is_finite() or amount <= 0 or credits['unit'] != 'USD':
            raise ValueError('Free plan credits are unavailable')
    except (KeyError, TypeError, InvalidOperation, OverflowError, AttributeError) as error:
        raise ValueError('Free account plan could not be verified; no deployment allowed') from error
    return True
