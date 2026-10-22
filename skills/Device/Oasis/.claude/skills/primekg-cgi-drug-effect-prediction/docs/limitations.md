# Limitations

1. This handoff only supports drugs already present in `prepared/candidate_pool.csv`.
2. It does not support arbitrary SMILES, new DrugBank IDs, KG-external natural products, or MCE library cold start.
3. Graph CGI e50 uses learned PrimeKG compound nodes and graph context; an external molecule lacks this fitted compound node and CGI neighborhood.
4. Scores are for research ranking and prioritization, not clinical treatment recommendations.
5. The package does not retrain the model and does not include CMI or feedback-model fine-tuning.

For KG-external compounds, build a separate cold-start or structure-adaptation layer before using the Graph CGI scoring head.
