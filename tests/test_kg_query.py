from openanalog.forge.knowledge_graph import KnowledgeGraph


def test_parse_spec_query():
    filters = KnowledgeGraph.parse_spec_query("TIA BW>1MHz power<2mW")
    assert filters.get("topology") == "tia"
    assert filters.get("bw_MHz>") == 1.0
    assert filters.get("power_mW<") == 2.0


def test_query_ranks_matching_nodes():
    kg = KnowledgeGraph()
    kg.g.clear()
    kg.add_node(
        "tia",
        "netlist_a",
        {},
        {"bw_MHz": 2.0, "power_mW": 1.5, "gain_dB": 60},
        fitness_pass_rate=0.9,
        generation=100,
    )
    kg.add_node(
        "tia",
        "netlist_b",
        {},
        {"bw_MHz": 0.5, "power_mW": 5.0, "gain_dB": 40},
        fitness_pass_rate=0.2,
        generation=50,
    )
    results = kg.query("TIA BW>1MHz power<2mW", top=2)
    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]
