#!/usr/bin/env python3

"""KOReader Sync Plugin for Calibre."""

import os
from functools import partial

from calibre.constants import DEBUG as _DEBUG
from calibre.constants import numeric_version
from calibre.customize import InterfaceActionBase
from calibre.devices.usbms.driver import debug_print as root_debug_print
from calibre.utils.config import JSONConfig

__license__ = 'GNU GPLv3'
__copyright__ = '2021, harmtemolder <mail at harmtemolder.com>'
__modified_by__ = 'kyxap kyxappp@gmail.com'
__modification_date__ = '2024'
__docformat__ = 'restructuredtext en'

DEBUG = _DEBUG
DRY_RUN = False  # Used during debugging to skip the actual updating of metadata
PYDEVD = False  # Used during debugging to connect to PyCharm's remote debugging

if numeric_version >= (5, 5, 0):
    module_debug_print = partial(
        root_debug_print,
        ' koreader:__init__:',
        sep=''
    )
else:
    module_debug_print = partial(root_debug_print, 'koreader:__init__:')


class KoreaderSync(InterfaceActionBase):
    name = 'KOReader Sync'
    description = 'Get metadata from a connected KOReader device'
    author = 'harmtemolder & others, currently maintaining by: kyxap'
    version = (0, 8, 0)
    version_string = '0.8.0'
    minimum_calibre_version = (5, 0, 1)  # Because Python 3
    config = JSONConfig(os.path.join('plugins', 'KOReader Sync.json'))
    actual_plugin = 'calibre_plugins.koreader.action:KoreaderAction'

    def is_customizable(self):
        return True

    def config_widget(self):
        if self.actual_plugin_:
            from calibre_plugins.koreader.config import \
                ConfigWidget  # pylint: disable=import-error, disable=import-outside-toplevel
            return ConfigWidget(self.actual_plugin_)
        return None

    def save_settings(self, config_widget):
        config_widget.save_settings()


def clean_bookmarks(bookmarks):
    """Transforms KOReader's bookmark metadata into text that can be stored
    in calibre. I assume that all bookmarks have a `note` attribute, which I
    use as the main text of the bookmark. All other attributes are stored in a
    HTML comment.

    :param bookmarks: dict with numbered keys and annotations dict values
    :return: HTML-formatted str of the all bookmarks and highlights
    """
    debug_print = partial(root_debug_print, 'clean_bookmarks:')

    # Dictionary to store highlights grouped by chapter
    highlights_by_chapter = {}

    for annotation in bookmarks.values():
        if 'note' not in annotation:
            debug_print('annotation does not have `note`', annotation)
        else:
            debug_print('annotation has `note`', annotation)

        # Extracting all attributes to save as hidden text
        hidden_attributes = ''
        if len(bookmarks) > 0:
            hidden_attributes += ' <!-- '
            for attr, val in annotation.items():
                hidden_attributes += f'{attr}: {val}, '
            hidden_attributes = hidden_attributes[:-2] + ' -->'
        hidden_attributes += '\n'

        # Extracting attributes that will be used in html
        chapter = annotation.get("chapter", "Unknown Chapter")
        reader_note = annotation.get("note", "no notes")
        highlighted_text = annotation.get("text", "Unknown Highlighted Text")
        datetime = annotation.get("datetime", "Unknown Datetime")

        # Create highlight dictionary
        highlight = {
            "chapter": chapter,
            "reader_note": reader_note,
            "highlighted_text": highlighted_text,
            "datetime": datetime,
            "hidden_attributes": hidden_attributes
        }

        # Add highlight to the corresponding chapter
        if chapter not in highlights_by_chapter:
            highlights_by_chapter[chapter] = []
        highlights_by_chapter[chapter].append(highlight)

    # Generate HTML content for each chapter
    html_content = ('<!DOCTYPE html>\n<html>\n<head>\n'
                    '<title>Book Highlights and Notes</title>\n'
                    '</head>\n<body>\n')
    highlight_count = 0
    for chapter, chapter_highlights in highlights_by_chapter.items():
        if chapter.strip() == '':
            chapter = 'Unknown'
        html_content += f'<div>\n<h3>Chapter: <u>{chapter}</u></h3>\n'
        html_content += '<blockquote>'

        for highlight in chapter_highlights:
            highlight_count += 1
            html_content += (f'<p><strong>{highlight_count}. Highlight</strong'
                             f'> - {highlight["datetime"]} '
                             f'<br/>{highlight["highlighted_text"]}\n')
            html_content += '<br><br>\n'
            html_content += ('<strong>Note:</strong> <i>'
                             f'{highlight["reader_note"]}</i></p>\n')
            html_content += f'{highlight["hidden_attributes"]}\n'

        html_content += "</div>\n"
        html_content += '</blockquote>'

    html_content += "</body>\n</html>"
    return html_content.strip()
