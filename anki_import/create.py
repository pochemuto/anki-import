from dataclasses import dataclass
import json
import os
from pprint import pprint
import re
from typing import cast
import anki
import gspread
from anki.collection import Collection
from anki.exporting import AnkiPackageExporter
from loguru import logger
import csv
import os
from bs4 import BeautifulSoup, element

article_template = re.compile(r"^(der|die|das|[esr]) ")
plurals = re.compile(r",\s+.*$")


@dataclass
class Card:
    ru: str
    de: str
    beispiel: str
    example_ru: str

    def uuid(self) -> str:
        uuid = self.de
        uuid = re.sub(article_template, "", uuid)
        uuid = re.sub(plurals, "", uuid)
        return uuid


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
        )
        data_list.append(data_obj)
    return data_list


def replace_article(string):
    pattern = re.compile(r"^(der|die|das)\s")
    return pattern.sub(
        lambda match: "r "
        if match.group(1) == "der"
        else "e "
        if match.group(1) == "die"
        else "s ",
        string,
    )


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

    # Create a new collection
    collection = Collection("collection.anki2")

    # Save and export the collection to an Anki package (.apkg) file
    deck_id = collection.decks.id("German")
    assert deck_id is not None
    deck = collection.decks.get(deck_id)

    model = collection.models.new("German Russian Cards")
    model["did"] = deck_id
    model["css"] = templates.css

    collection.models.addField(model, collection.models.new_field("De"))
    collection.models.addField(model, collection.models.new_field("DeExample"))
    collection.models.addField(model, collection.models.new_field("Ru"))
    collection.models.addField(model, collection.models.new_field("RuExample"))

    tmpl = collection.models.new_template("de -> ru")
    tmpl["qfmt"] = templates.templates["de2ru"].question
    tmpl["afmt"] = templates.templates["de2ru"].answer

    collection.models.addTemplate(model, tmpl)
    tmpl = collection.models.new_template("ru -> de")
    tmpl["qfmt"] = templates.templates["ru2de"].question
    tmpl["afmt"] = templates.templates["ru2de"].answer
    collection.models.addTemplate(model, tmpl)

    model["id"] = 3371927463  # essential for upgrade detection
    collection.models.update(model)
    collection.models.set_current(model)
    collection.models.save(model)

    for card in cards:
        note = anki.notes.Note(collection, model)
        note["De"] = replace_article(card.de)
        note["DeExample"] = card.beispiel
        note["Ru"] = card.ru
        note["RuExample"] = card.example_ru

        note.guid = card.uuid()
        collection.addNote(note)

    exporter = AnkiPackageExporter(collection)
    export_path = os.path.abspath("german.apkg")
    exporter.exportInto(export_path)
    logger.info("Saved to {}", export_path)


def main():
    logger.info("Creating apkg...")
    cards = read_spreadsheet()
    templates = read_templates()
    create_deck(cards, templates)
    logger.info("Done.")


if __name__ == "__main__":
    main()
