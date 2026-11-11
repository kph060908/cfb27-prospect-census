import unittest

from giveaway.draw import eligible, entry, field

BODY = """### League name

LFL

### Team

Tennessee

### Class year

2029

### Platform

PS5

### Your capture zip

[lfl-class2029.zip](https://github.com/user-attachments/files/123456/lfl-class2029.zip)

### TikTok handle (optional)

_No response_
"""


def issue(n, created, body=BODY, labels=()):
    return {"number": n, "createdAt": created, "body": body, "labels": [{"name": x} for x in labels]}


class DrawTests(unittest.TestCase):
    def test_fields(self):
        self.assertEqual(field(BODY, "League name"), "LFL")
        self.assertEqual(field(BODY, "Class year"), "2029")
        self.assertEqual(field(BODY, "TikTok handle (optional)"), "")

    def test_zip_found(self):
        self.assertEqual(entry(issue(1, "2026-11-12"))["zips"],
                         ["https://github.com/user-attachments/files/123456/lfl-class2029.zip"])

    def test_one_entry_per_league_class(self):
        pool = eligible([entry(issue(5, "2026-11-13")), entry(issue(2, "2026-11-12"))])
        self.assertEqual([e["number"] for e in pool], [2])

    def test_league_name_case_ignored(self):
        other = BODY.replace("\nLFL\n", "\nlfl\n")
        pool = eligible([entry(issue(2, "2026-11-12")), entry(issue(3, "2026-11-13", other))])
        self.assertEqual([e["number"] for e in pool], [2])

    def test_other_class_year_counts(self):
        other = BODY.replace("\n2029\n", "\n2030\n")
        pool = eligible([entry(issue(2, "2026-11-12")), entry(issue(3, "2026-11-13", other))])
        self.assertEqual([e["number"] for e in pool], [2, 3])

    def test_winners_invalid_and_zipless_sit_out(self):
        nozip = BODY.replace("https://github.com/user-attachments/files/123456/lfl-class2029.zip", "")
        pool = eligible([entry(issue(1, "2026-11-10", labels=["entry", "winner"])),
                         entry(issue(2, "2026-11-11", BODY.replace("LFL", "A"), labels=["entry", "invalid"])),
                         entry(issue(3, "2026-11-12", nozip.replace("LFL", "B"))),
                         entry(issue(4, "2026-11-13", BODY.replace("LFL", "C")))])
        self.assertEqual([e["number"] for e in pool], [4])


if __name__ == "__main__":
    unittest.main()
