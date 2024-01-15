import anki
from anki.collection import Collection
from anki.exporting import AnkiPackageExporter
# from anki.importing.csvfile import TextImporter

# Create a new collection
collection = Collection('my_collection.anki2')

# Create a new deck in the collection (otherwise the "Default") deck will be used
deck_id = collection.decks.id('Deck name')
model = collection.models.by_name('Basic')
model['did'] = deck_id
collection.models.save(model)

# # # Import cards from CSV into the new collection
# # importer = TextImporter('/path/to/test.csv')
# # importer.initMapping()
# # importer.run()

# Save and export the collection to an Anki package (.apkg) file
deck_id = collection.decks.id("_deck")
deck = collection.decks.get(deck_id)

model = collection.models.new("_model")
# model['tags'].append("_tag")
model['did'] = deck_id
model['css'] = """
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
"""

collection.models.addField(model, collection.models.newField('en'))
collection.models.addField(model, collection.models.newField('ru'))

tmpl = collection.models.newTemplate('en -> ru')
tmpl['qfmt'] = '<div class="from">{{en}}</div>'
tmpl['afmt'] = '{{FrontSide}}\n\n<hr id=answer>\n\n{{ru}}'
collection.models.addTemplate(model, tmpl)
tmpl = collection.models.newTemplate('ru -> en')
tmpl['qfmt'] = '{{ru}}'
tmpl['afmt'] = '{{FrontSide}}\n\n<hr id=answer>\n\n<div class="from">{{en}}</div>'
collection.models.addTemplate(model, tmpl)

model['id'] = 12345678  # essential for upgrade detection
collection.models.update(model)
collection.models.setCurrent(model)
collection.models.save(model)

note = anki.notes.Note(collection, model)
note['en'] = "hello"
note['ru'] = u"[heləʊ]\nint. привет"
note.guid = "xxx1"
collection.addNote(note)

note = collection.newNote()
note['en'] = "bye"
note['ru'] = u"[baɪ]\nint. пока"
note.guid = "xxx2"
collection.addNote(note)

exporter = AnkiPackageExporter(collection)
exporter.exportInto('my_deck.apkg')