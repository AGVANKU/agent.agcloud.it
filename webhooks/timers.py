"""
Timer triggers for scheduled tasks.

Registers timer-based triggers on the webhooks blueprint.
"""

import logging
from webhooks.webhooks import bp


@bp.timer_trigger(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False)
def health_ping_timer(timer) -> None:
    """
    Health ping timer - runs every 5 minutes.

    Placeholder for scheduled agent tasks. Replace or extend with:
    - Periodic data syncs
    - Queue cleanup
    - Scheduled agent executions
    """
    if timer.past_due:
        logging.warning("Health ping timer is past due")

    logging.info("Health ping timer fired")
