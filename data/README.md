# Data

Most data files in `data/` are not committed to this repository
because the audio files and pre-built vector indexes are too large
for Git. The catalog CSVs and other small metadata files **are**
committed and do not need to be downloaded separately.

To run the system locally, the following archives must be downloaded
and extracted:

**[AT-DJ Data Folder](https://drive.google.com/drive/folders/1B12Mn9hY1XV2Vutjd1TVMbfqQFrAtKqf?usp=drive_link)**

| File / Archive | Description | Extract to |
|---|---|---|
| `raw.zip` | Tango music MP3 files (the track catalog) | `data/raw/` |
| `cortinas.zip` | Pre-licensed cortina audio clips for pool fallback | `data/cortinas/` |
| `knowledge_base.zip` | Curated Markdown files for RAG domain knowledge | `data/knowledge_base/` |

Once extracted, build the ChromaDB index:

```bash
python -m atdj.rag.ingest --all --reset
```

The `data/chroma_db/` directory is created automatically by this step
and does not need to be downloaded.

The Drive folder also contains supplementary materials including a
demo video, presentation slides, and earlier feature exploration
notebooks.

---

## Domain Knowledge Sources

The Markdown files in `knowledge_base.zip` were compiled from the
following publicly available sources:

| Source | URL |
|---|---|
| Tango Delight — Difference between tango, milonga, and vals | https://tangodelight.com.au/the-difference-between-tango-milonga-and-vals-music/ |
| UNESCO Intangible Cultural Heritage — Tango | https://ich.unesco.org/en/RL/tango-00258 |
| TodoTango — Carlos Di Sarli | https://www.todotango.com/english/artists/info/17/Carlos-Di-Sarli |
| Tejas Tango — Building a Collection of Argentine Tango Music | https://www.tejastango.com/tango_music_collection.html |
| Tango Voice — DJ Fundamentals Part 2: Sequencing at a Milonga | https://tangovoice.wordpress.com/2017/05/31/tango-dj-fundamentals-part-2-managing-the-overall-sequencing-of-music-at-a-milonga/ |
| El Recodo — Tandas and Cortinas | https://www.el-recodo.com/tandascortinas-en?lang=en |

These sources were accessed in May 2026 and their content is
reproduced in the knowledge base for non-commercial research purposes
only.