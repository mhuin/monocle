# Monocle.
# Copyright (C) 2019-2020 Monocle authors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import re
from datetime import datetime

events_list = [
    'ChangeCreatedEvent',
    'ChangeAbandonEvent',
    'ChangeMergedEvent',
    'ChangeCommentedEvent',
    'ChangeReviewedEvent',
    'ChangeCommitPushedEvent',
    'ChangeCommitForcePushedEvent',
]


def date_to_epoch_ml(datestr):
    if not datestr:
        return None
    return int(datetime.strptime(datestr, "%Y-%m-%d").timestamp() * 1000)


def end_of_day_to_epoch_ml(datestr):
    if not datestr:
        return None
    return int(
        datetime.strptime(datestr + ' 23:59:59', "%Y-%m-%d %H:%M:%S").timestamp() * 1000
    )


def dbdate_to_datetime(datestr):
    return datetime.strptime(datestr, "%Y-%m-%dT%H:%M:%SZ")


def float_trunc(f, n=2):
    return float(int(f * 10 ** n)) / 10 ** n


class Detector(object):
    tests_regexp = ".*[Tt]est.*"
    tests_re = re.compile(tests_regexp)

    issue_tracker_links = {
        'generic': [
            {
                'regexp': '|'.join(
                    [
                        r'https?:\/\/.*issue.*',
                        r'https?:\/\/.*bug.*',
                        r'https?:\/\/.*jira.*',
                    ]
                ),
                'rewrite': None,
            }
        ],
        # https://help.github.com/en/github/writing-on-github/autolinked-references-and-urls
        'github.com': [
            {
                'regexp': r" #[0-9]+",
                'rewrite': {
                    'from': re.compile(r" #(?P<id>[0-9]+)"),
                    'to': "https://github.com/%(repository_prefix)s/%(repository_shortname)s/issues/%%(id)s",
                },
            },
            {
                'regexp': r"[^/ :]+\/[^/]+#[0-9]+",
                'rewrite': {
                    'from': re.compile(
                        r"(?P<org>[^/ :]+)\/(?P<repo>[^/]+)#(?P<id>[0-9]+)"
                    ),
                    'to': "https://github.com/%%(org)s/%%(repo)s/issues/%%(id)s",
                },
            },
            {
                'regexp': r"GH-[1-9]+",
                'rewrite': {
                    'from': re.compile(r"GH-(?P<id>[1-9]+)"),
                    'to': "https://github.com/%(repository_prefix)s/%(repository_shortname)s/issues/%%(id)s",
                },
            },
        ],
        'altassian.net': [
            {'regexp': r"https?:\/\/.+.atlassian.net\/browse\/.*", 'rewrite': None}
        ],
    }

    def is_tests_included(self, change):
        for file in change['changed_files']:
            if self.tests_re.match(file['path']):
                return True
        return False

    def get_issue_tracker_regexp(self, style='generic'):
        regexps = []
        for reg in self.issue_tracker_links.get(style, []):
            regexps.append(".*%s.*" % reg['regexp'].replace('#', r'\#'))
        regexp = "|".join(regexps)
        return regexp

    def issue_match_and_rewrite(self, change, field, reg):
        store = change['issue_tracker_links']
        r = re.compile(reg['regexp'])
        matches = r.findall(change[field])
        for match in matches:
            if not reg['rewrite']:
                # This is already a link. Do not rewrite
                store.append([match, match])
            else:
                m = reg['rewrite']['from'].match(match)
                if m:
                    # Format rewrite with change attributes
                    rewrite = reg['rewrite']['to'] % change
                    # Format rewrite with matched attributes
                    rewrite = rewrite % m.groupdict()
                    store.append([match.strip(), rewrite])

    def issue_tracker_extract_links(self, change):
        change['issue_tracker_links'] = []
        for tracker_regs in self.issue_tracker_links.values():
            for reg in tracker_regs:
                for field in ('title', 'text'):
                    self.issue_match_and_rewrite(change, field, reg)
        change['has_issue_tracker_links'] = (
            True if change['issue_tracker_links'] else False
        )

    def enhance(self, change):
        if change['type'] == 'Change':
            if self.is_tests_included(change):
                change['tests_included'] = True
            else:
                change['tests_included'] = False
            self.issue_tracker_extract_links(change)
        return change


def enhance_changes(changes):
    detector = Detector()
    changes = list(map(detector.enhance, changes))
    return changes


def set_params(input):
    def getter(attr, default):
        if isinstance(input, dict):
            return input.get(attr, default)
        else:
            return getattr(input, attr, default) or default

    params = {}
    params['gte'] = date_to_epoch_ml(getter('gte', None))
    params['lte'] = end_of_day_to_epoch_ml(getter('lte', None))
    params['on_cc_gte'] = date_to_epoch_ml(getter('on_cc_gte', None))
    params['on_cc_lte'] = end_of_day_to_epoch_ml(getter('on_cc_gte', None))
    params['ec_same_date'] = getter('ec_same_date', False)
    params['etype'] = getter('type', ','.join(events_list)).split(',')
    params['exclude_authors'] = getter('exclude_authors', None)
    params['authors'] = getter('authors', None)
    params['approval'] = getter('approval', None)
    params['size'] = int(getter('size', 10))
    params['from'] = int(getter('from', 0))
    params['files'] = getter('files', None)
    params['state'] = getter('state', None)
    params['tests_included'] = getter('tests_included', False)
    params['has_issue_tracker_links'] = getter('has_issue_tracker_links', None)
    params['change_ids'] = getter('change_ids', None)
    params['target_branch'] = getter('target_branch', None)
    if params['change_ids']:
        params['change_ids'] = params['change_ids'].split(',')
    if params['exclude_authors']:
        params['exclude_authors'] = params['exclude_authors'].split(',')
    if params['authors']:
        params['authors'] = params['authors'].split(',')
    return params
