from string import Template

telegram_warning_high = Template(
    """
⚠️ *WARNING*
`$PV` has surpassed `$LIMIT $EGU`
(Current value: `$VALUE $EGU`)
"""
)

telegram_warning_low = Template(
    """
⚠️ *WARNING*
`$PV` has gone below `$LIMIT $EGU`
(Current value: `$VALUE $EGU`)
"""
)

push_warning_high = Template(
    """
⚠️ $PV has surpassed $LIMIT $EGU (Current value: $VALUE $EGU)
"""
)

push_warning_low = Template(
    """
⚠️ $PV has gone below $LIMIT $EGU (Current value: $VALUE $EGU)
"""
)

hello = Template(
    """
Hello, *$NAME!*
If you've received this message, then you've configured SIMAR's EPICSTEL integration correctly.\n
For more information on how to use this bot, check out /help.
"""
)
