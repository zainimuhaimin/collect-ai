from pydantic import BaseModel, ConfigDict


class CustomerSummary(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"cust_id": "CUST-00029", "name": "CUST-00029", "active_contract_count": 1}}
    )

    cust_id: str
    name: str
    active_contract_count: int


class CustomerDetail(CustomerSummary):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cust_id": "CUST-00029",
                "name": "CUST-00029",
                "active_contract_count": 1,
                "b_list_status": "N",
                "behavioral_grade": "B",
            }
        }
    )

    b_list_status: str
    behavioral_grade: str
