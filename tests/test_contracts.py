from server.contracts import load_catalog, validate_contract


def test_all_example_contracts_valid():
    for c in load_catalog("contracts/medicare_contracts.json")["contracts"]:
        assert validate_contract(c) == []


def test_invalid_contract_reports_errors():
    c = load_catalog("contracts/medicare_contracts.json")["contracts"][0]
    broken = {**c, "signal": "telepathy"}
    assert validate_contract(broken) != []
