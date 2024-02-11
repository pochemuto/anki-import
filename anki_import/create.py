from bs4 import BeautifulSoup, element
from dataclasses import dataclass
from loguru import logger
from pprint import pprint
from typing import cast
import csv
import genanki
import gspread
import json
import os
import re

article_template = re.compile(r"^(der|die|das|[esr]) ")
plurals = re.compile(r",\s+.*$")


def remove_plurals(string: str) -> str:
    return re.sub(plurals, "", string)


def expand_article(string):
    pattern = re.compile(r"^(r|e|s)\s")
    return pattern.sub(
        lambda match: (
            "der "
            if match.group(1) == "d"
            else "die " if match.group(1) == "e" else "das "
        ),
        string,
    )


def collapse_article(string):
    pattern = re.compile(r"^(der|die|das)\s")
    return pattern.sub(
        lambda match: (
            "r "
            if match.group(1) == "der"
            else "e " if match.group(1) == "die" else "s "
        ),
        string,
    )


@dataclass
class Card:
    ru: str
    de: str
    beispiel: str
    example_ru: str
    type: str

    @property
    def uuid(self) -> str:
        uuid = self.de
        uuid = re.sub(article_template, "", uuid)
        uuid = remove_plurals(uuid)
        return uuid

    @property
    def de_speak(self) -> str:
        return expand_article(remove_plurals(self.de))

    @property
    def tags(self) -> list[str]:
        if not self.type:
            return []
        if len(self.type) <= 2:
            return []
        return [self.type]

def read_csv() -> list[Card]:
    csv_file_path = "Lernwortschatz.csv"
    data_list = []

    with open(csv_file_path, "r", encoding="utf-8") as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            data_obj = Card(
                de=row["DE"],
                ru=row["RU"],
                beispiel=row["Beispiel"],
                example_ru=row["Example"],
                type=row["Type"],
            )
            data_list.append(data_obj)

    return data_list


def read_spreadsheet() -> list[Card]:
    sh_key = "1IMquarJDdEsJUSYFOHIz_xRK4c-OGVR9Geqf5CH4ZjM"
    logger.info("Reading spreadsheet https://docs.google.com/spreadsheets/d/" + sh_key)
    auth = os.getenv("GOOGLE_SERVICE_ACCOUNT")
    if auth:
        logger.info("Found auth info in env")
        gc = gspread.service_account_from_dict(json.loads(auth))
    else:
        logger.info("Auth not found in env, using default")
        gc = gspread.service_account()
    sh = gc.open_by_key(sh_key)
    worksheet = sh.sheet1
    data_list = []
    records = worksheet.get_all_records()
    logger.info("Read {} records, last: {}", len(records), records[-1])
    for row in records:
        data_obj = Card(
            de=row["DE"],
            ru=row["RU"],
            beispiel=row["Beispiel"],
            example_ru=row["Example"],
            type=row["Type"]
        )
        data_list.append(data_obj)
    return data_list


@dataclass
class Template:
    name: str
    question: str
    answer: str


@dataclass
class Templates:
    css: str
    templates: dict[str, Template]


def parse_template(tag: element.Tag) -> Template:
    return Template(
        name=cast(str, tag.get("data-name")),
        question=cast(element.Tag, tag.find(class_="question")).prettify(),
        answer=cast(element.Tag, tag.find(class_="answer")).prettify(),
    )


def read_templates() -> Templates:
    script_path = os.path.abspath(__file__)
    templates_path = os.path.join(os.path.dirname(script_path), "templates.html")
    with open(templates_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    soup = BeautifulSoup(html_content, "html.parser")
    css = soup.find(id="css")
    assert css is not None

    templates: dict[str, Template] = {}
    for template_tag in soup.find_all(class_="template"):
        template = parse_template(template_tag)
        templates[template.name] = template
    return Templates(css=css.text, templates=templates)


def create_deck(cards: list[Card], templates: Templates):
    logger.info("Creating deck")

    class GermanNote(genanki.Note):
        @property
        def guid(self):
            return self._card.uuid

        @property
        def card(self) -> Card:
            return self._card

        @card.setter
        def card(self, card: Card):
            self._card = card

    deck = genanki.Deck(42223151, "German")
    model = genanki.Model(
        3371927463,
        "German Russian Cards",
        fields=[
            {"name": "De"},
            {"name": "DeExample"},
            {"name": "DeSpeak"},
            {"name": "Ru"},
            {"name": "RuExample"},
        ],
        css=templates.css,
        templates=[
            {
                "name": "de -> ru",
                "qfmt": templates.templates["de2ru"].question,
                "afmt": templates.templates["de2ru"].answer,
            },
            {
                "name": "ru -> de",
                "qfmt": templates.templates["ru2de"].question,
                "afmt": templates.templates["ru2de"].answer,
            },
        ],
    )
    deck.add_model(model)

    for card in cards:
        note = GermanNote(
            model=model,
            tags=card.tags,
            fields=[
                collapse_article(card.de),
                card.beispiel,
                card.de_speak,
                card.ru,
                card.example_ru,
            ],
        )
        note.card = card
        deck.add_note(note)

    export_path = os.path.abspath("german.apkg")
    genanki.Package(deck).write_to_file(export_path)
    logger.info("Saved to {}", export_path)


def main():
    logger.info("Creating apkg...")
    cards = read_spreadsheet()
    templates = read_templates()
    create_deck(cards, templates)
    logger.info("Done.")


if __name__ == "__main__":
    main()
