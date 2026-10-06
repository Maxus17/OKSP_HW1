import unittest
from datetime import date
from rules import overdue_days, fine, can_issue
class RulesTests(unittest.TestCase):
    def test_due_day(self): self.assertEqual(overdue_days(date(2026,1,1),today=date(2026,1,1)),0)
    def test_early_return(self): self.assertEqual(fine(date(2026,1,5),date(2026,1,1)),0)
    def test_late_return(self): self.assertEqual(fine(date(2026,1,1),date(2026,1,4)),30)
    def test_active_overdue(self): self.assertEqual(overdue_days(date(2026,1,1),today=date(2026,1,3)),2)
    def test_busy(self): self.assertFalse(can_issue(True,False))
    def test_overdue_reader(self): self.assertFalse(can_issue(False,True))
    def test_available(self): self.assertTrue(can_issue(False,False))
