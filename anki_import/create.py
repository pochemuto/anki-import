from dataclasses import dataclass
import json
import os
from pprint import pprint
import re
import anki
import gspread
from anki.collection import Collection
from anki.exporting import AnkiPackageExporter
from loguru import logger
import csv

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
    sh_key = '1IMquarJDdEsJUSYFOHIz_xRK4c-OGVR9Geqf5CH4ZjM'
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


def create_deck(cards: list[Card]):
    logger.info("Creating deck")

    # Create a new collection
    collection = Collection("collection.anki2")

    # Save and export the collection to an Anki package (.apkg) file
    deck_id = collection.decks.id("German")
    assert deck_id is not None
    deck = collection.decks.get(deck_id)

    model = collection.models.new("German Russian Cards")
    model["did"] = deck_id
    model[
        "css"
    ] = """
  .card {
    font-family: arial;
    font-size: 20px;
    text-align: center;
    color: black;
    background-color: white;
  }
  .from {
    font-style: italic;
  }
  .example_de {
    font-size: 15px;
    color: gray
  }
  """

    collection.models.addField(model, collection.models.new_field("de"))
    collection.models.addField(model, collection.models.new_field("example_de"))
    collection.models.addField(model, collection.models.new_field("ru"))
    collection.models.addField(model, collection.models.new_field("example_ru"))

    tmpl = collection.models.new_template("de -> ru")
    tmpl[
        "qfmt"
    ] = '<div class="from">{{de}}<div class="example_de">{{example_de}}</div></div>'
    tmpl["afmt"] = "{{FrontSide}}\n\n<hr id=answer>\n\n{{ru}}"
    collection.models.addTemplate(model, tmpl)
    tmpl = collection.models.new_template("ru -> de")
    tmpl["qfmt"] = "{{ru}}"
    tmpl["afmt"] = '{{FrontSide}}\n\n<hr id=answer>\n\n<div class="from">{{de}}</div>'
    collection.models.addTemplate(model, tmpl)

    model["id"] = 3371927463  # essential for upgrade detection
    collection.models.update(model)
    collection.models.set_current(model)
    collection.models.save(model)

    for card in cards:
        note = anki.notes.Note(collection, model)
        note["de"] = replace_article(card.de)
        note["ru"] = card.ru
        note["example_de"] = card.beispiel
        note["example_ru"] = card.example_ru

        note.guid = card.uuid()
        collection.addNote(note)

    exporter = AnkiPackageExporter(collection)
    export_path = os.path.abspath("german.apkg")
    exporter.exportInto(export_path)
    logger.info("Saved to {}", export_path)



def main():
    logger.info("Creating apkg...")
    cards = read_spreadsheet()
    create_deck(cards)
    logger.info("Done.")

if __name__ == '__main__':
    main()