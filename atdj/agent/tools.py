import pandas as pd
from langchain_core.tools import tool
from atdj.config import CATALOG_PATH
from atdj.rag.select_tanda_old import select_tanda as _select_tanda
from atdj.rag.prompt_to_features import build_translator, load_catalog


def _load_catalog() -> pd.DataFrame:
    return pd.read_csv(CATALOG_PATH)


@tool
def search_catalog_rag(prompt: str) -> list[dict]:
    """Search catalog using RAG-powered tanda selection.
    Takes a natural language prompt and returns the best matching tanda."""
    from atdj.config import REDUCED_CATALOG_PATH, get_ui_provider, get_ui_api_key, get_ui_model
    provider = get_ui_provider()
    api_key = get_ui_api_key()
    model = get_ui_model()
    try:
        df = load_catalog(str(REDUCED_CATALOG_PATH))
        translator = build_translator(
            df, provider=provider.lower(),
            api_key=api_key,
            model_name=model,
        )
        bundle = translator.translate(prompt)
        result = _select_tanda(bundle, df)
        if result and result.tanda:
            return [t for t in result.tanda]
        return []
    except Exception as e:
        # Include UI provider/key state so issues with session-state propagation
        # are visible in the Session Log warning entry.
        return [{"error": f"{e} [provider={provider!r}, model={model!r}, key_set={bool(api_key)}]"}]

@tool
def select_cortina(
    preceding_style: str,
    duration_seconds: float = 20.0,
) -> dict:
    """Select a cortina from the catalog to follow a tanda."""
    df = _load_catalog()
    cortinas = df[df["style"] == "cortina"]
    if cortinas.empty:
        return {
            "filename": "default_cortina",
            "file_path": "data/cortinas/default.mp3",
            "duration_seconds": duration_seconds
        }
    cortina = cortinas.sample(1).iloc[0]
    return cortina.to_dict()