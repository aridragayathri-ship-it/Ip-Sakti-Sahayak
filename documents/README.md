# Documents folder

Drop your source PDFs here — Acts, guidelines, regulations, etc.
For example:

- Patents_Act_1970.pdf
- AYUSH_Guidelines.pdf
- Biological_Diversity_Act_2002.pdf

The backend (`backend/pdf_search.py`) scans this folder automatically
every time it starts — there's nothing to register or configure.
Filenames don't matter; any `.pdf` file placed here will be indexed.

If this folder is empty (as it is right now), `/api/ask` will always
return "Insufficient evidence in the current knowledge base." — that's
expected, not a bug. Add real PDFs here to see grounded answers.
