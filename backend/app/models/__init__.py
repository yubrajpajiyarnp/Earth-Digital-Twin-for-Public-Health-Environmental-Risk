"""Every analytical and AI model in the Nepal hydro-geological disaster digital twin.

  simulation/disaster_ml.py   local scikit-learn engine: flood discharge regressors,
                              landslide classifier, slope stability, surge detection,
                              interactive simulator, historical collinearity
  forecasting/holt_winters.py statistical baseline used for surge detection
  risk/knowledge_graph.py     driver -> hazard/health outcome graph
  llm/                        local Mistral (Ollama) narratives — phrases numbers, never computes them
  registry.py                 one catalogue of all of the above, runnable by name

Raw data fetching lives in app/ingestion/, not here.
"""
