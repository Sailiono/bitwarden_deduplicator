import unittest
import os
import tempfile

import pandas as pd

from bitwarden_deduplicator import (
    deduplicate_bitwarden_csv,
    deduplicate_dataframe,
)


COLUMNS = [
    'folder',
    'favorite',
    'type',
    'name',
    'notes',
    'fields',
    'reprompt',
    'login_uri',
    'login_username',
    'login_password',
    'login_totp',
]


def login_row(**overrides):
    row = {
        'folder': '',
        'favorite': '0',
        'type': 'login',
        'name': 'Example',
        'notes': '',
        'fields': '',
        'reprompt': '0',
        'login_uri': 'https://example.com/login',
        'login_username': 'alice',
        'login_password': 'secret',
        'login_totp': '',
    }
    row.update(overrides)
    return row


class SafeDeduplicationTests(unittest.TestCase):
    def test_removes_exact_duplicate_rows(self):
        row = login_row()
        result, stats = deduplicate_dataframe(
            pd.DataFrame([row, row], columns=COLUMNS)
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(stats['exact_duplicate_rows_removed'], 1)
        self.assertEqual(stats['conflicting_groups_retained'], 0)

    def test_preserves_conflicting_metadata(self):
        rows = [
            login_row(notes='first note'),
            login_row(notes='different note'),
        ]
        result, stats = deduplicate_dataframe(pd.DataFrame(rows, columns=COLUMNS))

        self.assertEqual(len(result), 2)
        self.assertEqual(stats['rows_removed'], 0)
        self.assertEqual(stats['conflicting_groups_retained'], 1)
        self.assertEqual(set(result['notes']), {'first note', 'different note'})

    def test_merges_blank_and_nonblank_metadata(self):
        rows = [
            login_row(notes=''),
            login_row(notes='preserved note'),
        ]
        result, stats = deduplicate_dataframe(pd.DataFrame(rows, columns=COLUMNS))

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['notes'], 'preserved note')
        self.assertEqual(stats['compatible_groups_merged'], 1)

    def test_domain_mode_does_not_add_helper_column(self):
        rows = [
            login_row(login_uri='https://example.com/login'),
            login_row(login_uri='https://example.com/account'),
        ]
        result, stats = deduplicate_dataframe(
            pd.DataFrame(rows, columns=COLUMNS),
            domain_only=True,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(list(result.columns), COLUMNS)
        self.assertNotIn('domain', result.columns)
        self.assertEqual(stats['compatible_groups_merged'], 1)

    def test_csv_output_round_trips_with_private_permissions(self):
        row = login_row()
        with tempfile.TemporaryDirectory() as directory:
            input_path = os.path.join(directory, 'input.csv')
            output_path = os.path.join(directory, 'output.csv')
            pd.DataFrame([row, row], columns=COLUMNS).to_csv(
                input_path,
                index=False,
                encoding='utf-8-sig',
            )

            deduplicate_bitwarden_csv(input_path, output_path)

            result = pd.read_csv(
                output_path,
                encoding='utf-8-sig',
                keep_default_na=False,
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(list(result.columns), COLUMNS)
            if os.name == 'posix':
                self.assertEqual(os.stat(output_path).st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
