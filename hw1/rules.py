from datetime import date

def overdue_days(due, returned=None, today=None):
    return max(0, ((returned or today or date.today()) - due).days)

def fine(due, returned=None, today=None, daily_rate=10):
    return overdue_days(due, returned, today) * daily_rate

def can_issue(busy, overdue):
    return not busy and not overdue
