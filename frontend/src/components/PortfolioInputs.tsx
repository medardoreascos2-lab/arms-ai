"use client";

export type PortfolioFormValues = {
  symbols: string;
  volatilities: string;
  expectedReturns: string;
  currentWeights: string;
  riskFreeRate: number;
};

type PortfolioInputsProps = {
  values: PortfolioFormValues;
  onChange: (
    values: PortfolioFormValues
  ) => void;
};

export function PortfolioInputs({
  values,
  onChange,
}: PortfolioInputsProps) {
  function update(
    field: keyof PortfolioFormValues,
    value: string | number
  ) {
    onChange({
      ...values,
      [field]: value,
    });
  }

  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-slate-50 p-5">
      <h3 className="text-lg font-semibold text-slate-900">
        Portfolio Inputs
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Introduce valores separados por comas y en el mismo orden.
      </p>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <InputField
          label="Assets"
          value={values.symbols}
          placeholder="AAPL, MSFT, NVDA"
          onChange={(value) =>
            update("symbols", value)
          }
        />

        <InputField
          label="Volatilities"
          value={values.volatilities}
          placeholder="0.20, 0.18, 0.35"
          onChange={(value) =>
            update("volatilities", value)
          }
        />

        <InputField
          label="Expected returns"
          value={values.expectedReturns}
          placeholder="0.12, 0.10, 0.18"
          onChange={(value) =>
            update("expectedReturns", value)
          }
        />

        <InputField
          label="Current weights (%)"
          value={values.currentWeights}
          placeholder="40, 35, 25"
          onChange={(value) =>
            update("currentWeights", value)
          }
        />

        <label className="block">
          <span className="text-sm font-medium text-slate-700">
            Risk-free rate
          </span>

          <input
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-blue-500"
            type="number"
            step="0.001"
            value={values.riskFreeRate}
            onChange={(event) =>
              update(
                "riskFreeRate",
                Number(event.target.value)
              )
            }
          />
        </label>
      </div>
    </section>
  );
}

function InputField({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">
        {label}
      </span>

      <input
        className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-blue-500"
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(event) =>
          onChange(event.target.value)
        }
      />
    </label>
  );
}
