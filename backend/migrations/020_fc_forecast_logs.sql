-- FarmNex AI forecaster connector: log of every forecast answer.
--
-- Safety: this file only ADDS one new `fc_`-prefixed table and its indexes, and turns on
-- row-level security for it. It never touches an existing table. Running it twice is a no-op.
--
-- Run this once, by hand, in the Supabase SQL editor. Nothing in this repo runs it automatically.

BEGIN;

CREATE TABLE IF NOT EXISTS public.fc_forecast_logs (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_public_id   UUID,                 -- FarmNex users.public_id, no FK on purpose
    kind             TEXT NOT NULL CHECK (kind IN ('price','demand','sell_options','crops')),
    request          JSONB NOT NULL,
    response         JSONB NOT NULL,
    data_as_of       DATE
);

CREATE INDEX IF NOT EXISTS fc_forecast_logs_user_idx ON public.fc_forecast_logs (user_public_id, created_at DESC);
CREATE INDEX IF NOT EXISTS fc_forecast_logs_kind_idx ON public.fc_forecast_logs (kind, created_at DESC);

ALTER TABLE public.fc_forecast_logs ENABLE ROW LEVEL SECURITY;  -- no policies: only the backend reads/writes

COMMIT;
