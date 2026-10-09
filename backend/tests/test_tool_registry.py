from app.agents.tool_registry import ToolRegistry


def test_tool_schema_is_specific_for_storage_capacity(db_session):
    registry = ToolRegistry(db_session)
    storage_schema = next(schema for schema in registry.schemas() if schema["function"]["name"] == "get_storage_capacity")
    parameters = storage_schema["function"]["parameters"]

    assert parameters["required"] == ["warehouse_id"]
    assert set(parameters["properties"]) == {"warehouse_id"}
    assert parameters["additionalProperties"] is False


def test_tool_registry_filters_extra_arguments(db_session, scenario_one):
    registry = ToolRegistry(db_session)

    output = registry.execute(
        "get_storage_capacity",
        {
            "warehouse_id": scenario_one["warehouse"].id,
            "product_id": scenario_one["product"].id,
            "quantity": 650,
        },
    )

    assert output["warehouse_id"] == scenario_one["warehouse"].id
    assert "current_occupied_volume" in output
    assert "available_storage_volume" in output
