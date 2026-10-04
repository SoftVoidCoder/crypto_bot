# RegimeFlow (Freqtrade) — image for Render.com.
#
# The official image already contains Freqtrade, TA-Lib and the `technical`
# package, so the strategy's `talib.abstract` / `technical.qtpylib` imports
# resolve without compiling anything at build time.
#
# One image serves every mode; the BOT_MODE environment variable selects the
# config overlay (see docker/entrypoint.sh):
#   dry      -> config.base.json                    (simulation, no keys)
#   testnet  -> config.base.json + config.testnet.json  (Bybit sandbox)
#   mainnet  -> config.base.json + config.mainnet.json  (real money, locked)
FROM freqtradeorg/freqtrade:stable

USER root

COPY --chown=ftuser:ftuser ft_user_data/config.base.json    /freqtrade/user_data/config.base.json
COPY --chown=ftuser:ftuser ft_user_data/config.testnet.json /freqtrade/user_data/config.testnet.json
COPY --chown=ftuser:ftuser ft_user_data/config.mainnet.json /freqtrade/user_data/config.mainnet.json
COPY --chown=ftuser:ftuser ft_user_data/strategies/         /freqtrade/user_data/strategies/
COPY --chown=ftuser:ftuser docker/entrypoint.sh             /freqtrade/docker-entrypoint.sh
COPY --chown=ftuser:ftuser docker/ru-translate.js           /freqtrade/docker/ru-translate.js
COPY --chown=ftuser:ftuser docker/inject-ui-translation.py  /freqtrade/docker/inject-ui-translation.py

# FreqUI ships English-only (no i18n, no locale files), so bake a small DOM
# translator into the page it serves instead of forking the app.
RUN set -eux; \
    IDX="$(find / -path '*/freqtrade/rpc/api_server/ui/installed/index.html' -not -path '/proc/*' 2>/dev/null | head -n 1)"; \
    if [ -n "$IDX" ]; then \
      python3 /freqtrade/docker/inject-ui-translation.py "$IDX" /freqtrade/docker/ru-translate.js \
        || echo "WARNING: Russian UI injection failed; FreqUI stays English"; \
    else \
      echo "WARNING: FreqUI index.html not found; skipping Russian UI injection"; \
    fi

RUN chmod +x /freqtrade/docker-entrypoint.sh \
 && mkdir -p /freqtrade/user_data/data /freqtrade/user_data/logs \
 && chown -R ftuser:ftuser /freqtrade/user_data

USER ftuser
WORKDIR /freqtrade

ENV BOT_MODE=dry

# Render injects PORT; Freqtrade's api_server is pointed at it by the entrypoint.
EXPOSE 10000

ENTRYPOINT ["/freqtrade/docker-entrypoint.sh"]
