# AT-DJ End-to-End Debug Pipeline Example

**Output of runniing from rag folder `python debug_one_tanda.py --prompt "energetic D'Arienzo tango, fast and danceable"`**

> NOTE: 
> This is an example of what's actually going on in our pipeline behind the scene \(˶╹◡╹˶)ﾉ❁ :

## Terminal Output

```text
════════════════════════════════════════════════════════════════════════
AT-DJ  end-to-end debug pipeline
════════════════════════════════════════════════════════════════════════
  Prompt   : "energetic D'Arienzo tango, fast and danceable"
  CSV      : ../../data/reduced_catalog.csv
  Provider : gemini
  Top-N    : 15

════════════════════════════════════════════════════════════════════════
STEP 0 — Load catalog
════════════════════════════════════════════════════════════════════════
  Rows : 294
  Cols : 22
  Columns: ['id', 'title', 'orchestra', 'singer', 'year', 'decade', 'style', 'duration_seconds', 'combo_key', 'album', 'filename', 'bpm', 'bpm_label', 'danceability', 'danceability_label', 'key', 'chords_changes_rate', 'chords_changes_rate_label', 'energy', 'energy_label', 'tags', 'file_path']
  chords_changes_rate_label: sample='high'  ← label col (used for soft-filter)
  chords_changes_rate: sample=np.float64(0.0831732079386711)  ← raw float (used for scoring)
  Style distribution: {'tango': 216, 'vals': 41, 'milonga': 37}

  ⏱  Step 0 elapsed: 0.006s


════════════════════════════════════════════════════════════════════════
STEP 1 — Layer 1: regex extraction (year / decade)
════════════════════════════════════════════════════════════════════════
  Prompt : "energetic D'Arienzo tango, fast and danceable"
  → year   = None
  → decade = None

════════════════════════════════════════════════════════════════════════
STEP 2 — Layer 2: LLM extraction  (provider='gemini')
════════════════════════════════════════════════════════════════════════
  ⚠  Could not call LLM translator: ValueError: Missing GEMINI_API_KEY
  → Falling back to regex-only bundle (all LLM fields = None).

  Fallback merged: {
    "year": null,
    "decade": null,
    "orchestra": null,
    "singer": null,
    "style": null,
    "album": null,
    "bpm_label": "moderate",
    "danceability_label": "moderate",
    "key": null,
    "chords_changes_rate": "moderate",
    "energy_label": "moderate",
    "tags": []
}

  ⏱  Steps 1+2 elapsed: 1.842s

════════════════════════════════════════════════════════════════════════
STEP 3 — Hard filter  (style, decade, orchestra, singer, album, year)
════════════════════════════════════════════════════════════════════════
  [style]  skipped (null)
  [decade]  skipped (null)
  [orchestra]  skipped (null)
  [singer]  skipped (null)
  [album]  skipped (null)

  ✦ Hard filter result: 294 tracks

  ⏱  Step 3 elapsed: 0.000s


════════════════════════════════════════════════════════════════════════
STEP 4 — Soft filter  (bpm_label, danceability_label, key, energy_label, chords)
════════════════════════════════════════════════════════════════════════
  Style=None → tanda size needed = 4
  [bpm_label='moderate']  294 → 73  ✓
  [danceability_label='moderate']  73 → 20  ✓
  [key]  skipped (null)
  [energy_label='moderate']  20 → 11  ✓
  [chords_changes_rate='moderate' via 'chords_changes_rate_label']  11 → 4

  ✦ Soft filter result: 4 tracks
  → CASE B: no viable group in soft pool. Falling back to hard pool (294 tracks).

  ⏱  Step 4 elapsed: 0.003s


════════════════════════════════════════════════════════════════════════
STEP 5 — Scoring  (numeric feature proximity + tag similarity)
════════════════════════════════════════════════════════════════════════
  Weights          : {'bpm': 0.2, 'danceability': 0.2, 'chords': 0.15, 'energy': 0.2, 'tags': 0.25}
  Label→percentile : {'slow': 0.25, 'low': 0.25, 'moderate': 0.5, 'fast': 0.75, 'high': 0.75, 'very fast': 0.9}

  Catalog feature ranges (used for scoring):
    bpm                : [90.88,  184.57]
    danceability       : [0.8348, 1.3098]
    chords_changes_rate: [0.0323, 0.1111]
    energy             : [0.1167, 0.9161]

  Numeric targets derived from labels:
    bpm                  label='moderate'   → p50 = 137.7267
    danceability         label='moderate'   → p50 = 1.0723
    chords               label='moderate'   → p50 = 0.0717
    energy               label='moderate'   → p50 = 0.5164

  Query tags: []
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Loading weights: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 103/103 [00:00<00:00, 16761.59it/s]
BertModel LOAD REPORT from: sentence-transformers/all-MiniLM-L6-v2
Key                     | Status     |  | 
------------------------+------------+--+-
embeddings.position_ids | UNEXPECTED |  | 

Notes:
- UNEXPECTED:   can be ignored when loading from different task/architecture; not ok if you expect identical arch.
  sentence-transformers: AVAILABLE ✓ (using cosine similarity)

  Top 15 candidates (sorted by composite score):
  Title                               Orchestra              Combo key                       bpm  dan  crd  eng  tag  → comp
  ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  La Copa Del Olvido                  Ricardo Tanturi        ricardo tanturi | alberto castillo | tango  0.92 0.99 0.99 1.00 0.16  → 0.7676
  Comparsa Criolla                    Ricardo Tanturi        ricardo tanturi | instrumental | tango  0.98 0.99 0.95 0.91 0.16  → 0.7587
  Es Mejor Perdonar                   Pedro Laurenz          pedro laurenz | juan carlos casas | tango  0.91 0.96 0.94 0.99 0.19  → 0.7573
  Decile Que Vuelva                   Ricardo Tanturi        ricardo tanturi | alberto castillo | tango  0.91 0.96 0.96 0.95 0.16  → 0.7460
  Guapeando                           Anibal Troilo          anibal troilo | instrumental | tango  0.97 0.98 0.94 0.81 0.20  → 0.7416
  Soy Muchacho De La Guardia          Anibal Troilo          anibal troilo | francisco fiorentino | tango  0.90 0.99 0.89 0.93 0.16  → 0.7384
  Infamia                             Juan D'Arienzo         juan d'arienzo | héctor mauré | tango  0.97 0.96 0.99 0.95 0.05  → 0.7370
  Al Verla Pasar                      Pedro Laurenz          pedro laurenz | juan carlos casas | tango  0.88 0.93 0.93 0.93 0.20  → 0.7359
  Telon                               Lucio Demare           lucio demare | carlos miranda | tango  0.84 1.00 0.91 0.89 0.20  → 0.7331
  Shusheta                            Carlos Di Sarli        carlos di sarli | instrumental | tango  1.00 0.87 0.90 0.96 0.13  → 0.7328
  Tierrita                            Juan D'Arienzo         juan d'arienzo | héctor mauré | tango  1.00 0.88 0.87 0.94 0.16  → 0.7325
  En La Buena Y En La Mala            Enrique Rodriguez      enrique rodriguez | armando moreno | tango  0.99 1.00 0.99 0.74 0.15  → 0.7313
  Altar Sin Luz                       Alfredo De Angelis     alfredo de angelis | julio martel | tango  0.84 0.99 0.86 0.99 0.14  → 0.7284
  La Abandone Y No Sabia              Ricardo Tanturi        ricardo tanturi | enrique campos | tango  0.91 0.99 0.99 0.84 0.13  → 0.7274
  Como Has Cambiado Pebeta            Enrique Rodriguez      enrique rodriguez | armando moreno | tango  0.87 1.00 0.79 0.98 0.15  → 0.7265
  ⏱  Step 5 elapsed: 4.732s


════════════════════════════════════════════════════════════════════════
STEP 6 — Tanda grouping + best combination
════════════════════════════════════════════════════════════════════════
  Style=None → tanda size = 4

  All combo_key groups in scored pool:
    alfredo de angelis | carlos dante-julio martel | tango    4 tracks  ✓ eligible
      top scores: [0.6933, 0.6917, 0.6857, 0.6822]
    alfredo de angelis | carlos dante-julio martel | vals    5 tracks  ✓ eligible
      top scores: [0.6533, 0.596, 0.5854, 0.5817, 0.5587]
    alfredo de angelis | floreal ruiz | tango    5 tracks  ✓ eligible
      top scores: [0.696, 0.6736, 0.6584, 0.6318, 0.6311]
    alfredo de angelis | instrumental | tango    6 tracks  ✓ eligible
      top scores: [0.698, 0.6742, 0.6664, 0.6651, 0.6296]
    alfredo de angelis | julio martel | tango    6 tracks  ✓ eligible
      top scores: [0.7284, 0.6714, 0.6698, 0.6527, 0.6102]
    alfredo gobbi | instrumental | tango        6 tracks  ✓ eligible
      top scores: [0.683, 0.6639, 0.6569, 0.6382, 0.5969]
    angel d'agostino | angel vargas | milonga    5 tracks  ✓ eligible
      top scores: [0.6478, 0.6452, 0.6441, 0.6426, 0.6181]
    angel d'agostino | angel vargas | tango     6 tracks  ✓ eligible
      top scores: [0.7158, 0.7032, 0.6488, 0.6193, 0.6147]
    angel d'agostino | angel vargas | vals      4 tracks  ✓ eligible
      top scores: [0.6444, 0.6341, 0.6236, 0.5813]
    angel d'agostino | instrumental | tango     4 tracks  ✓ eligible
      top scores: [0.692, 0.6339, 0.6156, 0.5418]
    anibal troilo | alberto marino | milonga    3 tracks  ✓ eligible
      top scores: [0.6484, 0.6242, 0.6132]
    anibal troilo | alberto marino | tango      6 tracks  ✓ eligible
      top scores: [0.7148, 0.6785, 0.6528, 0.6494, 0.6309]
    anibal troilo | floreal ruiz | tango        6 tracks  ✓ eligible
      top scores: [0.6943, 0.6885, 0.6728, 0.6671, 0.6571]
    anibal troilo | francisco fiorentino | milonga    5 tracks  ✓ eligible
      top scores: [0.674, 0.6701, 0.6444, 0.6407, 0.5885]
    anibal troilo | francisco fiorentino | tango    6 tracks  ✓ eligible
      top scores: [0.7384, 0.723, 0.6613, 0.6547, 0.6259]
    anibal troilo | francisco fiorentino | vals    5 tracks  ✓ eligible
      top scores: [0.6895, 0.6531, 0.6509, 0.6029, 0.546]
    anibal troilo | instrumental | tango        6 tracks  ✓ eligible
      top scores: [0.7416, 0.7252, 0.6834, 0.6576, 0.6487]
    carlos di sarli | alberto podestá | tango    6 tracks  ✓ eligible
      top scores: [0.686, 0.6581, 0.6573, 0.6563, 0.6535]
    carlos di sarli | instrumental | tango      6 tracks  ✓ eligible
      top scores: [0.7328, 0.6836, 0.6423, 0.6035, 0.5565]
    carlos di sarli | jorge durán | tango       6 tracks  ✓ eligible
      top scores: [0.6645, 0.6325, 0.6292, 0.612, 0.5911]
    carlos di sarli | roberto rufino | milonga    6 tracks  ✓ eligible
      top scores: [0.6804, 0.6334, 0.6224, 0.6146, 0.6067]
    carlos di sarli | roberto rufino | tango    6 tracks  ✓ eligible
      top scores: [0.6985, 0.6908, 0.6818, 0.6466, 0.6369]
    enrique rodriguez | armando moreno | tango    6 tracks  ✓ eligible
      top scores: [0.7313, 0.7265, 0.7258, 0.6953, 0.6875]
    francisco canaro | ernesto famá | milonga    3 tracks  ✓ eligible
      top scores: [0.6105, 0.5644, 0.497]
    francisco canaro | instrumental | milonga    4 tracks  ✓ eligible
      top scores: [0.6659, 0.6344, 0.583, 0.5766]
    francisco canaro | instrumental | tango     4 tracks  ✓ eligible
      top scores: [0.6684, 0.6234, 0.5956, 0.5671]
    francisco canaro | instrumental | vals      5 tracks  ✓ eligible
      top scores: [0.6344, 0.6054, 0.5948, 0.5673, 0.5488]
    juan d'arienzo | alberto echagüe | milonga    8 tracks  ✓ eligible
      top scores: [0.6987, 0.6537, 0.6464, 0.6152, 0.6092]
    juan d'arienzo | alberto echagüe | tango    6 tracks  ✓ eligible
      top scores: [0.7008, 0.691, 0.6826, 0.6759, 0.6646]
    juan d'arienzo | alberto echagüe/armando laborde | vals    3 tracks  ✓ eligible
      top scores: [0.6199, 0.6046, 0.569]
    juan d'arienzo | héctor mauré | tango       6 tracks  ✓ eligible
      top scores: [0.737, 0.7325, 0.708, 0.6874, 0.6675]
    juan d'arienzo | instrumental | tango       6 tracks  ✓ eligible
      top scores: [0.7227, 0.7075, 0.7062, 0.7034, 0.6494]
    juan d'arienzo | instrumental | vals       13 tracks  ✓ eligible
      top scores: [0.654, 0.6141, 0.6121, 0.6087, 0.6073]
    lucio demare | carlos miranda | tango       4 tracks  ✓ eligible
      top scores: [0.7331, 0.7208, 0.715, 0.7139]
    lucio demare | raúl berón | tango           6 tracks  ✓ eligible
      top scores: [0.6849, 0.6731, 0.6576, 0.6293, 0.6207]
    miguel caló | raúl berón | tango            6 tracks  ✓ eligible
      top scores: [0.7021, 0.6973, 0.6901, 0.6856, 0.6782]
    miguel caló | raúl iriarte | tango          6 tracks  ✓ eligible
      top scores: [0.7112, 0.6854, 0.6844, 0.6708, 0.6507]
    osvaldo fresedo | instrumental | tango      5 tracks  ✓ eligible
      top scores: [0.6705, 0.6633, 0.6589, 0.6532, 0.602]
    osvaldo fresedo | ricardo ruiz | tango      6 tracks  ✓ eligible
      top scores: [0.6955, 0.6927, 0.6772, 0.6541, 0.6515]
    osvaldo fresedo | roberto ray | tango       6 tracks  ✓ eligible
      top scores: [0.6754, 0.6741, 0.6703, 0.6534, 0.6333]
    osvaldo pugliese | alberto morán | tango    6 tracks  ✓ eligible
      top scores: [0.7129, 0.7041, 0.6574, 0.6101, 0.5991]
    osvaldo pugliese | instrumental | tango     6 tracks  ✓ eligible
      top scores: [0.6774, 0.6578, 0.6173, 0.5841, 0.5831]
    osvaldo pugliese | roberto chanel | tango    6 tracks  ✓ eligible
      top scores: [0.7041, 0.7027, 0.696, 0.6956, 0.6875]
    pedro laurenz | alberto podestá | tango     6 tracks  ✓ eligible
      top scores: [0.7036, 0.6768, 0.6733, 0.6541, 0.6509]
    pedro laurenz | instrumental | tango        4 tracks  ✓ eligible
      top scores: [0.7225, 0.7205, 0.6887, 0.6473]
    pedro laurenz | juan carlos casas | tango    6 tracks  ✓ eligible
      top scores: [0.7573, 0.7359, 0.7104, 0.7069, 0.703]
    ricardo tanturi | alberto castillo | milonga    3 tracks  ✓ eligible
      top scores: [0.6904, 0.6006, 0.5963]
    ricardo tanturi | alberto castillo | tango    6 tracks  ✓ eligible
      top scores: [0.7676, 0.746, 0.7066, 0.6948, 0.6873]
    ricardo tanturi | alberto castillo | vals    6 tracks  ✓ eligible
      top scores: [0.6293, 0.613, 0.612, 0.6091, 0.5911]
    ricardo tanturi | enrique campos | tango    6 tracks  ✓ eligible
      top scores: [0.7274, 0.6783, 0.6768, 0.6731, 0.6683]
    ricardo tanturi | instrumental | tango      6 tracks  ✓ eligible
      top scores: [0.7587, 0.7132, 0.6957, 0.6626, 0.6527]
    rodolfo biagi | instrumental | tango        6 tracks  ✓ eligible
      top scores: [0.701, 0.6537, 0.6506, 0.6475, 0.6081]
    tipica victor | instrumental | tango        6 tracks  ✓ eligible
      top scores: [0.6766, 0.6679, 0.6648, 0.6385, 0.6335]

  ★ BEST TANDA  combo_key='ricardo tanturi | alberto castillo | tango'  mean_score=0.7288

  1. La Copa Del Olvido                     | Ricardo Tanturi        | 1940s | bpm=very fast  dance=high       energy=moderate   score=0.7676
  2. Decile Que Vuelva                      | Ricardo Tanturi        | 1940s | bpm=very fast  dance=moderate   energy=low        score=0.7460
  3. Al Compas De Un Tango                  | Ricardo Tanturi        | 1940s | bpm=very fast  dance=high       energy=moderate   score=0.7066
  4. A Otra Cosa Che Pebeta                 | Ricardo Tanturi        | 1940s | bpm=fast       dance=moderate   energy=moderate   score=0.6948

  ⏱  Step 6 elapsed: 0.174s

════════════════════════════════════════════════════════════════════════
⏱  TIMING SUMMARY
════════════════════════════════════════════════════════════════════════
  Step 0  load catalog            0.006s  █
  Steps 1+2  prompt → LLM         1.842s  ████████
  Step 3  hard filter             0.000s  █
  Step 4  soft filter             0.003s  █
  Step 5  scoring                 4.732s  █████████████████████
  Step 6  tanda grouping          0.174s  █
  TOTAL (wall clock)              6.757s
════════════════════════════════════════════════════════════════════════
Done.
════════════════════════════════════════════════════════════════════════
```
