(genai-atdj) (base) nancyma@Mac genai-atdj % uv run python atdj/rag/debug_select_tanda.py --csv data/reduced_catalog.csv

──────────────────────────────────────────────────────────────────────
AT-DJ select_tanda DEBUG
──────────────────────────────────────────────────────────────────────
Merged bundle:
{
  "year": null,
  "decade": null,
  "orchestra": null,
  "singer": null,
  "style": "tango",
  "album": null,
  "bpm_label": "fast",
  "danceability_label": "high",
  "key": null,
  "chords_changes_rate": "moderate",
  "energy_label": "high",
  "tags": [
    "energetic",
    "driving rhythm",
    "percussive",
    "intense",
    "technical"
  ]
}

──────────────────────────────────────────────────────────────────────
STEP 0 — Load catalog
──────────────────────────────────────────────────────────────────────
  Total rows: 294
  Columns:    ['id', 'title', 'orchestra', 'singer', 'year', 'decade', 'style', 'duration_seconds', 'combo_key', 'album', 'filename', 'bpm', 'bpm_label', 'danceability', 'danceability_label', 'key', 'chords_changes_rate', 'chords_changes_rate_label', 'energy', 'energy_label', 'tags', 'file_path']

  chords_changes_rate_label sample: 'high'  ← use this for filtering
  chords_changes_rate sample:       np.float64(0.0831732079386711)  ← raw float, NOT for filtering

──────────────────────────────────────────────────────────────────────
STEP 1 — What vals tracks exist in the catalog?
──────────────────────────────────────────────────────────────────────
  Total vals tracks: 41
  decade distribution:
    {'1940s': 18, '1930s': 4, '1950s': 3, '2000s': 1, '1970s': 1, '1920s': 1, '1960s': 1}
  bpm_label distribution:
    {'slow': 38, 'very fast': 2, 'moderate': 1}
  danceability_label distribution:
    {'moderate': 17, 'low': 15, 'high': 9}
  energy_label distribution:
    {'high': 22, 'moderate': 11, 'low': 8}
  chords_changes_rate_label distribution:
    {'low': 23, 'moderate': 10, 'high': 8}

  vals + 1940s: 18 tracks
  bpm_label × danceability_label × energy_label cross-tab:
    bpm=slow       dance=high       energy=high       chords=low
    bpm=slow       dance=moderate   energy=moderate   chords=moderate
    bpm=slow       dance=moderate   energy=high       chords=high
    bpm=slow       dance=low        energy=moderate   chords=moderate
    bpm=slow       dance=moderate   energy=moderate   chords=high
    bpm=slow       dance=moderate   energy=high       chords=moderate
    bpm=slow       dance=low        energy=high       chords=moderate
    bpm=slow       dance=low        energy=high       chords=high
    bpm=slow       dance=low        energy=low        chords=low
    bpm=slow       dance=low        energy=moderate   chords=low
    bpm=slow       dance=high       energy=high       chords=moderate

  Prompt wants: bpm=fast  dance=high  energy=high  chords=moderate

──────────────────────────────────────────────────────────────────────
STEP 2 — Hard filter  (style, decade, orchestra, singer, album, year)
──────────────────────────────────────────────────────────────────────
  [style='tango'] 294 → 216 tracks  ✓

  Hard filter result: 216 tracks

──────────────────────────────────────────────────────────────────────
STEP 3 — Soft filter  (bpm_label, danceability_label, key, chords_changes_rate, energy_label)
──────────────────────────────────────────────────────────────────────
  [bpm_label='fast'] 216 → 73 tracks  ✓
  [danceability_label='high'] 73 → 20 tracks  ✓
  [energy_label='high'] 20 → 10 tracks  ✓
  [chords_changes_rate='moderate' via chords_changes_rate_label] 10 → 5 tracks

  Soft filter result: 5 tracks
  No viable combo_key group (need ≥4 tracks per group).
  → CASE C: falling back to hard-filter pool (216 tracks)

──────────────────────────────────────────────────────────────────────
STEP 4 — Tag similarity (Jaccard fallback + optional sentence-transformers)
──────────────────────────────────────────────────────────────────────
  Query tags: ['energetic', 'driving rhythm', 'percussive', 'intense', 'technical']

Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Loading weights: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 103/103 [00:00<00:00, 8497.68it/s]
BertModel LOAD REPORT from: sentence-transformers/all-MiniLM-L6-v2
Key                     | Status     |  | 
------------------------+------------+--+-
embeddings.position_ids | UNEXPECTED |  | 

Notes:
- UNEXPECTED:   can be ignored when loading from different task/architecture; not ok if you expect identical arch.
  sentence-transformers: AVAILABLE ✓
  Title                               Track tags                                          Jaccard  {'CosSim':>8}
  ────────────────────────────────────────────────────────────────────────────────────────────────────
  Pastora                             ['reggae', 'drums', 'literate', 'poignant', 'wistful', 'bittersweet', 'autumnal', 'brooding', 'sad']   0.0000    0.1581
  Remolino                            ['literate', 'poignant', 'wistful', 'bittersweet', 'autumnal', 'brooding', 'happy']   0.0000    0.0825
  Fruto Dulce                         ['reggae', 'jazz', 'drums', 'experimental', 'literate', 'poignant', 'wistful', 'bittersweet', 'autumnal', 'brooding', 'sad']   0.0000    0.1981
  Pregonera                           ['jazz', 'drums', 'popfolk', 'literate', 'poignant', 'wistful', 'bittersweet', 'autumnal', 'brooding']   0.0000    0.1778
  Como Se Muere De Amor               ['orchestral', 'strings', 'soundtrack', 'jazz', 'film', 'violin', 'ambient', 'drums', 'literate', 'poignant', 'wistful', 'bittersweet', 'autumnal', 'brooding', 'sad']   0.0000    0.1779
  Mi Novia De Ayer                    ['reggae', 'jazz', 'popfolk', 'rollicking', 'cheerful', 'fun', 'sweet', 'amiable', 'good', 'natured', 'happy']   0.0000    0.1641
  Dejame Asi                          ['orchestral', 'strings', 'soundtrack', 'jazz', 'film', 'violin', 'ambient', 'experimental', 'literate', 'poignant', 'wistful', 'bittersweet', 'autumnal', 'brooding']   0.0000    0.1642
  Bajo El Cono Azul                   ['orchestral', 'strings', 'soundtrack', 'film', 'violin', 'drums', 'literate', 'poignant', 'wistful', 'bittersweet', 'autumnal', 'brooding', 'sad', 'happy']   0.0000    0.1389

──────────────────────────────────────────────────────────────────────
STEP 5 — Score every candidate  (numeric feature values, not labels)
──────────────────────────────────────────────────────────────────────
  Weights: {'bpm': 0.2, 'danceability': 0.2, 'chords': 0.15, 'energy': 0.2, 'tags': 0.25}
  Label → percentile: {'slow': 0.25, 'low': 0.25, 'moderate': 0.5, 'fast': 0.75, 'high': 0.75, 'very fast': 0.9}

  Catalog feature ranges:
    bpm:                [90.88,  184.57]
    danceability:       [0.8348, 1.3098]
    chords_changes_rate:[0.0323, 0.1111]
    energy:             [0.1167, 0.9161]

  Numeric targets derived from labels:
    bpm                  label=fast       → p75 = 161.1486
    danceability         label=high       → p75 = 1.1910
    chords               label=moderate   → p50 = 0.0717
    energy               label=high       → p75 = 0.7162

Loading weights: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 103/103 [00:00<00:00, 16666.54it/s]
BertModel LOAD REPORT from: sentence-transformers/all-MiniLM-L6-v2
Key                     | Status     |  | 
------------------------+------------+--+-
embeddings.position_ids | UNEXPECTED |  | 

Notes:
- UNEXPECTED:   can be ignored when loading from different task/architecture; not ok if you expect identical arch.
  Title                               Orch                      bpm   dan   crd   eng   tag  → comp
  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  El Taladro                          Alfredo De Angelis        0.59  0.98  0.82  0.95  0.38  → 0.7225
  Abandono                            Pedro Laurenz             0.66  0.88  1.00  0.97  0.21  → 0.7016
  Amurado                             Pedro Laurenz             0.70  0.82  0.97  0.97  0.23  → 0.7011
  Llorar Por Una Mujer                Enrique Rodriguez         0.67  0.97  0.88  0.95  0.20  → 0.7009
  En La Buena Y En La Mala            Enrique Rodriguez         0.74  0.75  0.99  0.99  0.22  → 0.7006
  Orgullo Criollo                     Pedro Laurenz             0.65  0.91  0.95  0.86  0.26  → 0.6916
  El Ciruja                           Alfredo De Angelis        0.62  0.93  0.93  0.99  0.15  → 0.6840
  Barajando                           Juan D'Arienzo            0.65  0.91  0.90  0.86  0.26  → 0.6821
  Cordon De Oro                       Anibal Troilo             0.70  0.77  0.91  0.95  0.23  → 0.6794
  No Me Extraña                       Pedro Laurenz             0.72  0.84  0.82  0.94  0.21  → 0.6764
  Como Se Pianta La Vida              Enrique Rodriguez         0.77  0.64  0.95  0.98  0.22  → 0.6743
  Cancion De Rango                    Ricardo Tanturi           0.62  0.83  0.93  0.97  0.20  → 0.6711
  Guapeando                           Anibal Troilo             0.72  0.77  0.94  0.94  0.15  → 0.6669
  Che Papusa Oi                       Tipica Victor             0.67  0.95  0.70  0.98  0.17  → 0.6664
  Bajo Belgrano                       Alfredo De Angelis        0.64  0.84  0.85  0.98  0.19  → 0.6657

──────────────────────────────────────────────────────────────────────
STEP 6 — Tanda grouping + best combination
──────────────────────────────────────────────────────────────────────
  Style='tango'  →  tanda size = 4

  combo_key groups with ≥4 tracks:
    'alfredo de angelis | carlos dante-julio martel | tango': 4 tracks, top scores: [0.6074, 0.5562, 0.5558, 0.5507]
    'alfredo de angelis | floreal ruiz | tango': 5 tracks, top scores: [0.6135, 0.5778, 0.5379, 0.5325, 0.5146]
    'alfredo de angelis | instrumental | tango': 6 tracks, top scores: [0.7225, 0.6625, 0.5683, 0.5566, 0.5427]
    'alfredo de angelis | julio martel | tango': 6 tracks, top scores: [0.684, 0.6657, 0.585, 0.5105, 0.4878]
    'alfredo gobbi | instrumental | tango': 6 tracks, top scores: [0.6158, 0.593, 0.5862, 0.5425, 0.4859]
    "angel d'agostino | angel vargas | tango": 6 tracks, top scores: [0.5811, 0.5466, 0.5466, 0.4962, 0.4816]
    "angel d'agostino | instrumental | tango": 4 tracks, top scores: [0.5403, 0.5263, 0.4988, 0.3758]
    'anibal troilo | alberto marino | tango': 6 tracks, top scores: [0.6134, 0.5961, 0.5785, 0.578, 0.5757]
    'anibal troilo | floreal ruiz | tango': 6 tracks, top scores: [0.607, 0.5528, 0.5438, 0.5292, 0.5011]
    'anibal troilo | francisco fiorentino | tango': 6 tracks, top scores: [0.6496, 0.626, 0.556, 0.5209, 0.4859]
    'anibal troilo | instrumental | tango': 6 tracks, top scores: [0.6794, 0.6669, 0.645, 0.631, 0.5864]
    'carlos di sarli | alberto podestá | tango': 6 tracks, top scores: [0.5476, 0.5453, 0.5253, 0.4891, 0.4784]
    'carlos di sarli | instrumental | tango': 6 tracks, top scores: [0.6343, 0.564, 0.5541, 0.4826, 0.4524]
    'carlos di sarli | jorge durán | tango': 6 tracks, top scores: [0.613, 0.5947, 0.5835, 0.5459, 0.5078]
    'carlos di sarli | roberto rufino | tango': 6 tracks, top scores: [0.6451, 0.5302, 0.5288, 0.4795, 0.4783]
    'enrique rodriguez | armando moreno | tango': 6 tracks, top scores: [0.7009, 0.7006, 0.6743, 0.6543, 0.5961]
    'francisco canaro | instrumental | tango': 4 tracks, top scores: [0.6531, 0.6392, 0.6158, 0.6108]
    "juan d'arienzo | alberto echagüe | tango": 6 tracks, top scores: [0.6821, 0.6523, 0.6425, 0.6422, 0.6419]
    "juan d'arienzo | héctor mauré | tango": 6 tracks, top scores: [0.6384, 0.6364, 0.6315, 0.6276, 0.6016]
    "juan d'arienzo | instrumental | tango": 6 tracks, top scores: [0.617, 0.5894, 0.5611, 0.5583, 0.5497]
    'lucio demare | carlos miranda | tango': 4 tracks, top scores: [0.6628, 0.6254, 0.6206, 0.5999]
    'lucio demare | raúl berón | tango': 6 tracks, top scores: [0.6056, 0.5768, 0.5628, 0.55, 0.5479]
    'miguel caló | raúl berón | tango': 6 tracks, top scores: [0.614, 0.6058, 0.5664, 0.5572, 0.5426]
    'miguel caló | raúl iriarte | tango': 6 tracks, top scores: [0.62, 0.5706, 0.5519, 0.5438, 0.4897]
    'osvaldo fresedo | instrumental | tango': 5 tracks, top scores: [0.6407, 0.6076, 0.5864, 0.5138, 0.4664]
    'osvaldo fresedo | ricardo ruiz | tango': 6 tracks, top scores: [0.6411, 0.6213, 0.5823, 0.5664, 0.5497]
    'osvaldo fresedo | roberto ray | tango': 6 tracks, top scores: [0.5655, 0.5325, 0.5181, 0.5058, 0.4881]
    'osvaldo pugliese | alberto morán | tango': 6 tracks, top scores: [0.5642, 0.5535, 0.5463, 0.5371, 0.4382]
    'osvaldo pugliese | instrumental | tango': 6 tracks, top scores: [0.5831, 0.575, 0.505, 0.4827, 0.4585]
    'osvaldo pugliese | roberto chanel | tango': 6 tracks, top scores: [0.6495, 0.6344, 0.5942, 0.5689, 0.546]
    'pedro laurenz | alberto podestá | tango': 6 tracks, top scores: [0.6491, 0.6402, 0.5734, 0.5728, 0.561]
    'pedro laurenz | instrumental | tango': 4 tracks, top scores: [0.6916, 0.6572, 0.6359, 0.6146]
    'pedro laurenz | juan carlos casas | tango': 6 tracks, top scores: [0.7016, 0.7011, 0.6764, 0.6358, 0.6302]
    'ricardo tanturi | alberto castillo | tango': 6 tracks, top scores: [0.6711, 0.6591, 0.6152, 0.6026, 0.5905]
    'ricardo tanturi | enrique campos | tango': 6 tracks, top scores: [0.6328, 0.6069, 0.6039, 0.5961, 0.58]
    'ricardo tanturi | instrumental | tango': 6 tracks, top scores: [0.6497, 0.6137, 0.5527, 0.5505, 0.5329]
    'rodolfo biagi | instrumental | tango': 6 tracks, top scores: [0.6251, 0.5972, 0.548, 0.5477, 0.4763]
    'tipica victor | instrumental | tango': 6 tracks, top scores: [0.6664, 0.646, 0.6179, 0.592, 0.5807]

  ★ Best tanda: enrique rodriguez | armando moreno | tango  mean_score=0.6825
    1. Llorar Por Una Mujer                | bpm=very fast  dance=high       energy=high       score=0.7009
    2. En La Buena Y En La Mala            | bpm=very fast  dance=high       energy=high       score=0.7006
    3. Como Se Pianta La Vida              | bpm=very fast  dance=moderate   energy=high       score=0.6743
    4. El Encopao                          | bpm=very fast  dance=high       energy=moderate   score=0.6543