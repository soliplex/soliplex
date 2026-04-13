"""Generative UI tools: render interactive widgets in the chat via tool calls.

The LLM calls these tools to produce structured JSON specs. The AG-UI
TOOL_CALL_RESULT carries the spec back to the Flutter frontend, which
renders the matching widget (form, chart, …) directly in the message list.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------


class FormField(BaseModel):
    """A single interactive form field."""

    label: str = Field(..., description="Display label shown above the input")
    field_type: Literal["text", "email", "number", "checkbox", "dropdown"] = Field(
        ...,
        description=(
            "Input kind: "
            "'text' — plain text input; "
            "'email' — email address input; "
            "'number' — numeric input; "
            "'checkbox' — yes/no toggle; "
            "'dropdown' — single choice from the 'options' list."
        ),
    )
    required: bool = Field(default=True, description="Whether the field is required")
    placeholder: Optional[str] = Field(
        default=None,
        description="Hint text shown inside text/email/number inputs",
    )
    options: Optional[list[str]] = Field(
        default=None,
        description="Required when field_type is 'dropdown': selectable values",
    )


class DynamicForm(BaseModel):
    title: str
    fields: list[FormField]
    submit_label: str = "Submit"


async def render_form(
    title: str,
    fields: list[FormField],
    submit_label: str = "Submit",
) -> str:
    """Render an interactive data-entry form in the chat.

    Call this tool whenever you need to collect structured input from the user.
    Do NOT describe the form in prose — call this tool directly.

    Supported field_type values: text, email, number, checkbox, dropdown.
    Use 'options' only for 'dropdown' fields.

    Example — contact form:
      render_form(
          title="Contact Us",
          fields=[
              {"label": "Name",     "field_type": "text",     "required": true},
              {"label": "Email",    "field_type": "email",    "required": true},
              {"label": "Priority", "field_type": "dropdown", "required": true,
               "options": ["Low", "Medium", "High"]},
          ]
      )

    Returns:
        JSON spec consumed by the frontend to render the form widget.
    """
    form = DynamicForm(title=title, fields=fields, submit_label=submit_label)
    return form.model_dump_json()


# ---------------------------------------------------------------------------
# Stock chart
# ---------------------------------------------------------------------------


class StockBar(BaseModel):
    """A single data bar in the stock chart."""

    label: str = Field(
        ...,
        description=(
            "Bar label — use a ticker symbol ('AAPL') or a time period "
            "('Mon', 'Jan', 'Q1')"
        ),
    )
    value: float = Field(..., description="Price or numeric value for this bar")


class StockChart(BaseModel):
    title: str
    symbol: str
    bars: list[StockBar]
    currency: str = "USD"


async def render_stock_chart(
    title: str,
    symbol: str,
    bars: list[StockBar],
    currency: str = "USD",
) -> str:
    """Render a stock price bar chart in the chat.

    Call this tool to display price data, trends, or comparisons visually.
    Do NOT use Markdown tables for financial figures — always call this tool.

    Example — weekly AAPL prices:
      render_stock_chart(
          title="AAPL — This Week",
          symbol="AAPL",
          bars=[
              {"label": "Mon", "value": 189.50},
              {"label": "Tue", "value": 191.20},
              {"label": "Wed", "value": 188.80},
              {"label": "Thu", "value": 190.10},
              {"label": "Fri", "value": 192.30},
          ]
      )

    Returns:
        JSON spec consumed by the frontend to render the chart widget.
    """
    chart = StockChart(title=title, symbol=symbol, bars=bars, currency=currency)
    return chart.model_dump_json()
