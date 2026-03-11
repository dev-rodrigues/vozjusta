#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
DURATION_MINUTES="${DURATION_MINUTES:-60}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-8}"
INTERVAL_JITTER_PCT="${INTERVAL_JITTER_PCT:-35}"
BURST_PROBABILITY_PCT="${BURST_PROBABILITY_PCT:-10}"
BURST_MIN_REQUESTS="${BURST_MIN_REQUESTS:-2}"
BURST_MAX_REQUESTS="${BURST_MAX_REQUESTS:-4}"
FOLLOWUP_PROBABILITY_PCT="${FOLLOWUP_PROBABILITY_PCT:-25}"
REQUEST_TIMEOUT_SECONDS="${REQUEST_TIMEOUT_SECONDS:-320}"
CACHE_HIT_PROBABILITY_PCT="${CACHE_HIT_PROBABILITY_PCT:-75}"
ERROR_BACKOFF_SECONDS="${ERROR_BACKOFF_SECONDS:-30}"
LOG_FILE="${LOG_FILE:-logs/popular_grafana_ask_load_$(date +%Y%m%d_%H%M%S).log}"

stop_requested=0
summary_printed=0
run_id="$(date +%Y%m%d%H%M%S)-$RANDOM"

theme_count_assedio_moral=0
theme_count_discriminacao_racial=0
theme_count_discriminacao_genero=0
theme_count_igualdade_salarial=0
theme_count_direitos_trabalhistas=0
theme_count_denuncia_discriminacao=0
theme_count_outros=0

total_requests=0
success_requests=0
error_requests=0
sum_latency=0
last_status_code=""
last_latency="0"

usage() {
  cat <<'EOF'
Uso: scripts/popular_grafana_ask_load.sh [opcoes]

Opcoes:
  -u, --base-url URL                    URL base da API (default: http://localhost:8000)
  -d, --duration-minutes N              Duracao total em minutos (default: 60)
  -i, --interval-seconds N              Intervalo base em segundos (default: 8)
      --jitter-pct N                    Variacao percentual do intervalo (default: 35)
      --burst-probability-pct N         Chance de rajada curta por ciclo (default: 10)
      --burst-min N                     Minimo de requests por rajada (default: 2)
      --burst-max N                     Maximo de requests por rajada (default: 4)
      --followup-probability-pct N      Chance de pergunta de continuidade (default: 25)
      --request-timeout-seconds N       Timeout maximo por request /ask (default: 320)
      --cache-hit-probability-pct N     Chance de repetir pergunta canonica (default: 75)
      --error-backoff-seconds N         Pausa extra apos erro/timeout (default: 30)
  -o, --log-file PATH                   Arquivo de log de execucao
  -h, --help                            Mostra esta ajuda

Variaveis de ambiente equivalentes:
  BASE_URL, DURATION_MINUTES, INTERVAL_SECONDS, INTERVAL_JITTER_PCT,
  BURST_PROBABILITY_PCT, BURST_MIN_REQUESTS, BURST_MAX_REQUESTS,
  FOLLOWUP_PROBABILITY_PCT, REQUEST_TIMEOUT_SECONDS,
  CACHE_HIT_PROBABILITY_PCT, ERROR_BACKOFF_SECONDS, LOG_FILE
EOF
}

is_number() {
  local value="$1"
  [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]]
}

is_integer() {
  local value="$1"
  [[ "$value" =~ ^[0-9]+$ ]]
}

clamp_int() {
  local value="$1"
  local min="$2"
  local max="$3"

  if [[ "$value" -lt "$min" ]]; then
    echo "$min"
    return
  fi
  if [[ "$value" -gt "$max" ]]; then
    echo "$max"
    return
  fi
  echo "$value"
}

escape_json() {
  local s="$1"
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  s=${s//$'\t'/\\t}
  printf '%s' "$s"
}

normalize_spaces() {
  printf '%s\n' "$1" | awk '{$1=$1; print}'
}

random_int() {
  local min="$1"
  local max="$2"
  if [[ "$max" -le "$min" ]]; then
    echo "$min"
    return
  fi
  echo $(( (RANDOM % (max - min + 1)) + min ))
}

weighted_pick() {
  local options=("$@")
  local item
  local weight
  local total=0
  local selected

  for item in "${options[@]}"; do
    weight="${item##*:}"
    if is_integer "$weight"; then
      total=$((total + weight))
    fi
  done

  if [[ "$total" -le 0 ]]; then
    echo "${options[0]%%:*}"
    return
  fi

  selected=$(( (RANDOM % total) + 1 ))
  for item in "${options[@]}"; do
    weight="${item##*:}"
    if ! is_integer "$weight"; then
      continue
    fi
    selected=$((selected - weight))
    if [[ "$selected" -le 0 ]]; then
      echo "${item%%:*}"
      return
    fi
  done

  echo "${options[0]%%:*}"
}

current_hour() {
  date +%H
}

current_weekday() {
  date +%u
}

is_peak_hour() {
  local hour
  hour="$(current_hour)"
  if (( (hour >= 9 && hour <= 12) || (hour >= 14 && hour <= 18) )); then
    return 0
  fi
  return 1
}

is_night_hour() {
  local hour
  hour="$(current_hour)"
  if (( hour < 7 || hour >= 22 )); then
    return 0
  fi
  return 1
}

is_weekend() {
  local weekday
  weekday="$(current_weekday)"
  if (( weekday >= 6 )); then
    return 0
  fi
  return 1
}

compute_interval_seconds() {
  local base="$INTERVAL_SECONDS"
  local multiplier="1.00"
  local jitter_value

  if is_peak_hour; then
    multiplier="0.70"
  elif is_night_hour; then
    multiplier="1.90"
  elif is_weekend; then
    multiplier="1.40"
  fi

  jitter_value=$(( RANDOM % (INTERVAL_JITTER_PCT * 2 + 1) - INTERVAL_JITTER_PCT ))
  awk -v b="$base" -v m="$multiplier" -v j="$jitter_value" '
    BEGIN {
      value = b * m * (1 + (j / 100.0));
      if (value < 0.8) value = 0.8;
      printf "%.2f", value;
    }'
}

compute_burst_pause_seconds() {
  local jitter_value
  jitter_value=$(( RANDOM % 91 - 45 ))
  awk -v b="$INTERVAL_SECONDS" -v j="$jitter_value" '
    BEGIN {
      value = (b * 0.22) * (1 + (j / 100.0));
      if (value < 0.6) value = 0.6;
      if (value > 2.5) value = 2.5;
      printf "%.2f", value;
    }'
}

compute_error_backoff_seconds() {
  local jitter_value
  jitter_value=$(( RANDOM % 61 - 30 ))
  awk -v b="$ERROR_BACKOFF_SECONDS" -v j="$jitter_value" '
    BEGIN {
      value = b * (1 + (j / 100.0));
      if (value < 5) value = 5;
      printf "%.2f", value;
    }'
}

should_followup() {
  local chance="$FOLLOWUP_PROBABILITY_PCT"
  if is_peak_hour; then
    chance=$((chance + 8))
  fi
  chance="$(clamp_int "$chance" 0 90)"

  if (( RANDOM % 100 < chance )); then
    return 0
  fi
  return 1
}

should_trigger_burst() {
  local theme="$1"
  local chance="$BURST_PROBABILITY_PCT"

  if is_peak_hour; then
    chance=$((chance + 8))
  fi

  if is_weekend; then
    chance=$((chance - 3))
  fi

  if [[ "$theme" == "denuncia_discriminacao" || "$theme" == "assedio_moral" ]]; then
    chance=$((chance + 4))
  fi

  chance="$(clamp_int "$chance" 0 80)"
  if (( RANDOM % 100 < chance )); then
    return 0
  fi
  return 1
}

pick_persona() {
  weighted_pick \
    "trabalhadora:32" \
    "testemunha:16" \
    "lider:10" \
    "rh:14" \
    "estudante:14" \
    "consultor_juridico:14"
}

pick_theme_for_persona() {
  local persona="$1"

  case "$persona" in
    trabalhadora)
      weighted_pick \
        "assedio_moral:21" \
        "discriminacao_racial:18" \
        "discriminacao_genero:16" \
        "igualdade_salarial:16" \
        "direitos_trabalhistas:14" \
        "denuncia_discriminacao:11" \
        "outros:4"
      ;;
    testemunha)
      weighted_pick \
        "denuncia_discriminacao:24" \
        "assedio_moral:22" \
        "discriminacao_racial:20" \
        "discriminacao_genero:14" \
        "direitos_trabalhistas:12" \
        "igualdade_salarial:4" \
        "outros:4"
      ;;
    lider)
      weighted_pick \
        "direitos_trabalhistas:20" \
        "igualdade_salarial:20" \
        "discriminacao_genero:18" \
        "assedio_moral:14" \
        "discriminacao_racial:14" \
        "denuncia_discriminacao:10" \
        "outros:4"
      ;;
    rh)
      weighted_pick \
        "igualdade_salarial:23" \
        "discriminacao_genero:20" \
        "assedio_moral:18" \
        "direitos_trabalhistas:16" \
        "discriminacao_racial:10" \
        "denuncia_discriminacao:9" \
        "outros:4"
      ;;
    estudante)
      weighted_pick \
        "direitos_trabalhistas:24" \
        "discriminacao_racial:18" \
        "discriminacao_genero:16" \
        "igualdade_salarial:16" \
        "denuncia_discriminacao:14" \
        "assedio_moral:8" \
        "outros:4"
      ;;
    consultor_juridico|*)
      weighted_pick \
        "denuncia_discriminacao:22" \
        "discriminacao_racial:20" \
        "discriminacao_genero:18" \
        "igualdade_salarial:16" \
        "direitos_trabalhistas:14" \
        "assedio_moral:8" \
        "outros:2"
      ;;
  esac
}

persona_prefix() {
  local persona="$1"
  case "$persona" in
    trabalhadora) echo "Sou trabalhadora de empresa privada." ;;
    testemunha) echo "Sou colega de trabalho e presenciei a situacao." ;;
    lider) echo "Sou lider de equipe e preciso orientar meu time." ;;
    rh) echo "Atuo no RH e preciso conduzir o caso corretamente." ;;
    estudante) echo "Sou estudante e estou pesquisando um caso pratico." ;;
    consultor_juridico) echo "Atuo com orientacao juridica preventiva para empresas." ;;
    *) echo "" ;;
  esac
}

pick_template_for_theme() {
  local theme="$1"
  local templates=()

  case "$theme" in
    assedio_moral)
      templates=(
        "O que caracteriza assedio moral no trabalho e quais provas devo reunir?"
        "Humilhacao recorrente em reuniao pode ser assedio moral?"
        "A empresa pode punir quem denuncia assedio moral?"
        "Como agir quando ha constrangimento publico por parte da chefia?"
        "Existe prazo para denunciar assedio moral no trabalho?"
        "A CLT protege o trabalhador em caso de assedio moral?"
      )
      ;;
    discriminacao_racial)
      templates=(
        "Discriminacao racial no trabalho e crime pela Lei 7.716/1989?"
        "Como agir diante de ofensa racista no ambiente de trabalho?"
        "O Estatuto da Igualdade Racial vale para relacoes de trabalho?"
        "Quais provas sao uteis em caso de racismo no emprego?"
        "A empresa responde quando ignora denuncia de preconceito racial?"
        "Posso denunciar racismo no trabalho ao MPT?"
      )
      ;;
    discriminacao_genero)
      templates=(
        "Demissao por gravidez pode configurar discriminacao de genero?"
        "Quais direitos a CLT garante contra discriminacao de genero?"
        "Como provar discriminacao de genero em promocao interna?"
        "A Lei 9.799/1999 protege mulheres no ambiente de trabalho?"
        "Tratamento desigual por maternidade e assedio discriminatorio?"
        "Discriminacao por identidade de genero no emprego gera indenizacao?"
      )
      ;;
    igualdade_salarial)
      templates=(
        "A Lei 14.611/2023 obriga igualdade salarial entre homens e mulheres?"
        "Como funciona equiparacao salarial na pratica?"
        "Quais documentos ajudam a provar salario desigual para mesma funcao?"
        "A empresa deve apresentar criterios de transparencia remuneratoria?"
        "Posso pedir revisao salarial por diferenca injustificada?"
        "Diferenca salarial por genero pode gerar multa para empresa?"
      )
      ;;
    direitos_trabalhistas)
      templates=(
        "Quais direitos trabalhistas me protegem contra discriminacao no trabalho?"
        "Quando devo procurar sindicato, MPT ou Defensoria?"
        "Posso ser demitido apos denunciar assedio ou discriminacao?"
        "Como registrar formalmente violacao de direitos trabalhistas?"
        "A CLT preve alguma estabilidade em casos de denuncia interna?"
        "Quais medidas imediatas reduzem risco de retaliacao no emprego?"
      )
      ;;
    denuncia_discriminacao)
      templates=(
        "Qual o primeiro passo para denunciar discriminacao no trabalho?"
        "Como denunciar assedio moral no MPT de forma segura?"
        "Existe canal anonimo para denunciar discriminacao no emprego?"
        "Quais orgaos oficiais recebem denuncia de racismo no trabalho?"
        "Como documentar um caso para denunciar com mais chance de sucesso?"
        "Posso denunciar mesmo sem testemunha direta?"
      )
      ;;
    outros|*)
      templates=(
        "Qual melhor horario para entrevista de emprego?"
        "Como melhorar meu curriculo para vaga junior?"
        "Que cursos ajudam a conseguir promocao?"
        "Como negociar aumento sem conflito?"
        "Dicas para falar em publico em reuniao."
      )
      ;;
  esac

  echo "${templates[$((RANDOM % ${#templates[@]}))]}"
}

pick_followup_for_theme() {
  local theme="$1"
  local snippets=()

  case "$theme" in
    assedio_moral)
      snippets=(
        "Tambem tenho receio de retaliacao depois da denuncia."
        "O caso acontece toda semana e ja tenho mensagens salvas."
      )
      ;;
    discriminacao_racial)
      snippets=(
        "Quero entender se cabe boletim de ocorrencia junto com denuncia trabalhista."
        "Tenho testemunhas, mas a empresa ainda nao respondeu."
      )
      ;;
    discriminacao_genero)
      snippets=(
        "O caso envolve comentarios ofensivos recorrentes no time."
        "Ja houve perda de oportunidade de promocao por esse motivo."
      )
      ;;
    igualdade_salarial)
      snippets=(
        "Tenho contracheques de colegas com funcao equivalente."
        "A diferenca salarial aparece mesmo com metas parecidas."
      )
      ;;
    direitos_trabalhistas)
      snippets=(
        "Quero saber a ordem correta de acao para nao perder prazo."
        "Tenho receio de denunciar e ser dispensado em seguida."
      )
      ;;
    denuncia_discriminacao)
      snippets=(
        "Preciso de um passo a passo simples para iniciar hoje."
        "Quero saber por onde comecar sem expor meus dados."
      )
      ;;
    outros|*)
      snippets=(
        "Se nao for tema juridico, qual canal oficial devo procurar?"
      )
      ;;
  esac

  echo "${snippets[$((RANDOM % ${#snippets[@]}))]}"
}

canonical_question_for_theme() {
  local theme="$1"
  case "$theme" in
    assedio_moral)
      echo "O que caracteriza assedio moral no trabalho?"
      ;;
    discriminacao_racial)
      echo "Discriminacao racial no trabalho e crime no Brasil?"
      ;;
    discriminacao_genero)
      echo "Demissao por gravidez pode ser discriminacao de genero?"
      ;;
    igualdade_salarial)
      echo "O que diz a Lei 14.611/2023 sobre igualdade salarial?"
      ;;
    direitos_trabalhistas)
      echo "Quais direitos trabalhistas protegem contra discriminacao no trabalho?"
      ;;
    denuncia_discriminacao)
      echo "Como denunciar discriminacao no trabalho de forma segura?"
      ;;
    outros|*)
      echo "Qual melhor horario para entrevista de emprego?"
      ;;
  esac
}

apply_natural_variation() {
  local text="$1"
  local roll

  roll=$((RANDOM % 100))
  if [[ "$roll" -lt 18 ]]; then
    text="No meu caso, $text"
  fi

  roll=$((RANDOM % 100))
  if [[ "$roll" -lt 12 ]]; then
    text="Por favor, $text"
  fi

  roll=$((RANDOM % 100))
  if [[ "$roll" -lt 14 ]]; then
    text="${text%\?}"
  fi

  roll=$((RANDOM % 100))
  if [[ "$roll" -lt 16 ]]; then
    text="$(printf '%s' "$text" | tr '[:upper:]' '[:lower:]')"
  fi

  echo "$text"
}

build_question() {
  local theme="$1"
  local persona="$2"
  local is_followup="$3"
  local use_cached_prompt=0
  local prefix
  local body
  local question

  if [[ "$is_followup" -eq 0 ]] && (( RANDOM % 100 < CACHE_HIT_PROBABILITY_PCT )); then
    use_cached_prompt=1
  fi

  if [[ "$use_cached_prompt" -eq 1 ]]; then
    question="$(canonical_question_for_theme "$theme")"
    echo "$question"
    return
  fi

  prefix="$(persona_prefix "$persona")"
  body="$(pick_template_for_theme "$theme")"

  if [[ "$is_followup" -eq 1 ]]; then
    body="$body $(pick_followup_for_theme "$theme")"
  fi

  question="$(normalize_spaces "$prefix $body")"
  question="$(apply_natural_variation "$question")"
  echo "$question"
}

increment_theme_counter() {
  local theme="$1"
  case "$theme" in
    assedio_moral) theme_count_assedio_moral=$((theme_count_assedio_moral + 1)) ;;
    discriminacao_racial) theme_count_discriminacao_racial=$((theme_count_discriminacao_racial + 1)) ;;
    discriminacao_genero) theme_count_discriminacao_genero=$((theme_count_discriminacao_genero + 1)) ;;
    igualdade_salarial) theme_count_igualdade_salarial=$((theme_count_igualdade_salarial + 1)) ;;
    direitos_trabalhistas) theme_count_direitos_trabalhistas=$((theme_count_direitos_trabalhistas + 1)) ;;
    denuncia_discriminacao) theme_count_denuncia_discriminacao=$((theme_count_denuncia_discriminacao + 1)) ;;
    *) theme_count_outros=$((theme_count_outros + 1)) ;;
  esac
}

on_interrupt() {
  stop_requested=1
  echo
  echo "[load] Interrupcao recebida. Finalizando com resumo parcial..."
}

print_summary() {
  if [[ "$summary_printed" -eq 1 ]]; then
    return
  fi
  summary_printed=1

  local avg_latency
  local success_rate

  if [[ "$total_requests" -gt 0 ]]; then
    avg_latency="$(awk -v sum="$sum_latency" -v total="$total_requests" 'BEGIN { printf "%.4f", (sum / total) }')"
    success_rate="$(awk -v ok="$success_requests" -v total="$total_requests" 'BEGIN { printf "%.2f", (ok * 100 / total) }')"
  else
    avg_latency="0.0000"
    success_rate="0.00"
  fi

  echo "[load] ---------------- Resumo ----------------"
  echo "[load] Run ID: ${run_id}"
  echo "[load] URL base: ${BASE_URL}"
  echo "[load] Duracao configurada (min): ${DURATION_MINUTES}"
  echo "[load] Intervalo base (s): ${INTERVAL_SECONDS}"
  echo "[load] Jitter intervalo (%): ${INTERVAL_JITTER_PCT}"
  echo "[load] Timeout por request (s): ${REQUEST_TIMEOUT_SECONDS}"
  echo "[load] Requisicoes totais: ${total_requests}"
  echo "[load] Sucesso (2xx): ${success_requests}"
  echo "[load] Falha (nao-2xx/erro): ${error_requests}"
  echo "[load] Taxa de sucesso (%): ${success_rate}"
  echo "[load] Latencia media (s): ${avg_latency}"
  echo "[load] Distribuicao simulada por tema:"
  echo "[load]   assedio_moral=${theme_count_assedio_moral}"
  echo "[load]   discriminacao_racial=${theme_count_discriminacao_racial}"
  echo "[load]   discriminacao_genero=${theme_count_discriminacao_genero}"
  echo "[load]   igualdade_salarial=${theme_count_igualdade_salarial}"
  echo "[load]   direitos_trabalhistas=${theme_count_direitos_trabalhistas}"
  echo "[load]   denuncia_discriminacao=${theme_count_denuncia_discriminacao}"
  echo "[load]   outros=${theme_count_outros}"
  echo "[load] Log: ${LOG_FILE}"
  echo "[load] ----------------------------------------"
}

request_once() {
  local question="$1"
  local persona="$2"
  local theme="$3"
  local request_kind="$4"
  local escaped_question
  local payload
  local response_file
  local curl_meta
  local status_code
  local latency
  local timestamp

  escaped_question="$(escape_json "$question")"
  payload="{\"question\":\"${escaped_question}\"}"
  response_file="$(mktemp)"

  curl_meta=""
  if curl_meta="$(curl -sS --max-time "$REQUEST_TIMEOUT_SECONDS" -o "$response_file" -w '%{http_code} %{time_total}' \
      -X POST "$ASK_URL" \
      -H 'accept: application/json' \
      -H 'Content-Type: application/json' \
      -d "$payload")"; then
    status_code="$(echo "$curl_meta" | awk '{print $1}')"
    latency="$(echo "$curl_meta" | awk '{print $2}')"
  else
    status_code="000"
    latency="0"
  fi

  rm -f "$response_file"

  total_requests=$((total_requests + 1))
  sum_latency="$(awk -v a="$sum_latency" -v b="$latency" 'BEGIN { printf "%.6f", (a + b) }')"

  increment_theme_counter "$theme"

  if [[ "$status_code" =~ ^2[0-9][0-9]$ ]]; then
    success_requests=$((success_requests + 1))
  else
    error_requests=$((error_requests + 1))
  fi

  last_status_code="$status_code"
  last_latency="$latency"

  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  printf '%s | run=%s | persona=%s | theme=%s | kind=%s | status=%s | latency_s=%s | question="%s"\n' \
    "$timestamp" "$run_id" "$persona" "$theme" "$request_kind" "$status_code" "$latency" "$question" | tee -a "$LOG_FILE"
}

parse_args() {
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      -u|--base-url)
        BASE_URL="$2"
        shift 2
        ;;
      -d|--duration-minutes)
        DURATION_MINUTES="$2"
        shift 2
        ;;
      -i|--interval-seconds)
        INTERVAL_SECONDS="$2"
        shift 2
        ;;
      --jitter-pct)
        INTERVAL_JITTER_PCT="$2"
        shift 2
        ;;
      --burst-probability-pct)
        BURST_PROBABILITY_PCT="$2"
        shift 2
        ;;
      --burst-min)
        BURST_MIN_REQUESTS="$2"
        shift 2
        ;;
      --burst-max)
        BURST_MAX_REQUESTS="$2"
        shift 2
        ;;
      --followup-probability-pct)
        FOLLOWUP_PROBABILITY_PCT="$2"
        shift 2
        ;;
      --request-timeout-seconds)
        REQUEST_TIMEOUT_SECONDS="$2"
        shift 2
        ;;
      --cache-hit-probability-pct)
        CACHE_HIT_PROBABILITY_PCT="$2"
        shift 2
        ;;
      --error-backoff-seconds)
        ERROR_BACKOFF_SECONDS="$2"
        shift 2
        ;;
      -o|--log-file)
        LOG_FILE="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "[load] Opcao invalida: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

parse_args "$@"

if ! is_number "$DURATION_MINUTES"; then
  echo "[load] DURATION_MINUTES invalido: ${DURATION_MINUTES}" >&2
  exit 1
fi

if ! is_number "$INTERVAL_SECONDS"; then
  echo "[load] INTERVAL_SECONDS invalido: ${INTERVAL_SECONDS}" >&2
  exit 1
fi

if ! is_integer "$INTERVAL_JITTER_PCT"; then
  echo "[load] INTERVAL_JITTER_PCT invalido: ${INTERVAL_JITTER_PCT}" >&2
  exit 1
fi

if ! is_integer "$BURST_PROBABILITY_PCT"; then
  echo "[load] BURST_PROBABILITY_PCT invalido: ${BURST_PROBABILITY_PCT}" >&2
  exit 1
fi

if ! is_integer "$BURST_MIN_REQUESTS" || ! is_integer "$BURST_MAX_REQUESTS"; then
  echo "[load] BURST_MIN_REQUESTS/BURST_MAX_REQUESTS devem ser inteiros." >&2
  exit 1
fi

if ! is_integer "$FOLLOWUP_PROBABILITY_PCT"; then
  echo "[load] FOLLOWUP_PROBABILITY_PCT invalido: ${FOLLOWUP_PROBABILITY_PCT}" >&2
  exit 1
fi

if ! is_number "$REQUEST_TIMEOUT_SECONDS"; then
  echo "[load] REQUEST_TIMEOUT_SECONDS invalido: ${REQUEST_TIMEOUT_SECONDS}" >&2
  exit 1
fi

if ! is_integer "$CACHE_HIT_PROBABILITY_PCT"; then
  echo "[load] CACHE_HIT_PROBABILITY_PCT invalido: ${CACHE_HIT_PROBABILITY_PCT}" >&2
  exit 1
fi

if ! is_number "$ERROR_BACKOFF_SECONDS"; then
  echo "[load] ERROR_BACKOFF_SECONDS invalido: ${ERROR_BACKOFF_SECONDS}" >&2
  exit 1
fi

if awk -v v="$DURATION_MINUTES" 'BEGIN { exit !(v > 0) }'; then :; else
  echo "[load] DURATION_MINUTES deve ser maior que zero." >&2
  exit 1
fi

if awk -v v="$INTERVAL_SECONDS" 'BEGIN { exit !(v > 0) }'; then :; else
  echo "[load] INTERVAL_SECONDS deve ser maior que zero." >&2
  exit 1
fi

if [[ "$BURST_MIN_REQUESTS" -gt "$BURST_MAX_REQUESTS" ]]; then
  echo "[load] BURST_MIN_REQUESTS nao pode ser maior que BURST_MAX_REQUESTS." >&2
  exit 1
fi

if awk -v v="$REQUEST_TIMEOUT_SECONDS" 'BEGIN { exit !(v > 0) }'; then :; else
  echo "[load] REQUEST_TIMEOUT_SECONDS deve ser maior que zero." >&2
  exit 1
fi

if awk -v v="$ERROR_BACKOFF_SECONDS" 'BEGIN { exit !(v > 0) }'; then :; else
  echo "[load] ERROR_BACKOFF_SECONDS deve ser maior que zero." >&2
  exit 1
fi

INTERVAL_JITTER_PCT="$(clamp_int "$INTERVAL_JITTER_PCT" 0 95)"
BURST_PROBABILITY_PCT="$(clamp_int "$BURST_PROBABILITY_PCT" 0 100)"
FOLLOWUP_PROBABILITY_PCT="$(clamp_int "$FOLLOWUP_PROBABILITY_PCT" 0 100)"
CACHE_HIT_PROBABILITY_PCT="$(clamp_int "$CACHE_HIT_PROBABILITY_PCT" 0 100)"

mkdir -p "$(dirname "$LOG_FILE")"

trap on_interrupt INT TERM
trap print_summary EXIT

BASE_URL="${BASE_URL%/}"
ASK_URL="${BASE_URL}/api/v1/ask"
HEALTH_URL="${BASE_URL}/api/v1/health"

if ! curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null 2>&1; then
  echo "[load] API indisponivel em ${HEALTH_URL}. Inicie a API antes de executar o script." >&2
  exit 1
fi

duration_seconds="$(awk -v m="$DURATION_MINUTES" 'BEGIN { printf "%.0f", (m * 60) }')"
end_epoch=$(( $(date +%s) + duration_seconds ))

echo "[load] Iniciando carga simulada (perfil organico)..."
echo "[load] Run ID: ${run_id}"
echo "[load] URL: ${ASK_URL}"
echo "[load] Duracao: ${DURATION_MINUTES} min"
echo "[load] Intervalo base: ${INTERVAL_SECONDS} s"
echo "[load] Jitter: ${INTERVAL_JITTER_PCT}%"
echo "[load] Burst chance: ${BURST_PROBABILITY_PCT}%"
echo "[load] Follow-up chance: ${FOLLOWUP_PROBABILITY_PCT}%"
echo "[load] Timeout por request: ${REQUEST_TIMEOUT_SECONDS}s"
echo "[load] Repeticao canonica (cache hit): ${CACHE_HIT_PROBABILITY_PCT}%"
echo "[load] Backoff apos erro: ${ERROR_BACKOFF_SECONDS}s"
echo "[load] Log: ${LOG_FILE}"

last_theme=""
last_persona=""
burst_sequence=0

while true; do
  now_epoch="$(date +%s)"
  if [[ "$stop_requested" -eq 1 ]] || [[ "$now_epoch" -ge "$end_epoch" ]]; then
    break
  fi

  persona=""
  theme=""
  request_kind="normal"
  followup_flag=0

  if [[ -n "$last_theme" ]] && should_followup; then
    persona="$last_persona"
    theme="$last_theme"
    request_kind="followup"
    followup_flag=1
  else
    persona="$(pick_persona)"
    theme="$(pick_theme_for_persona "$persona")"
  fi

  question="$(build_question "$theme" "$persona" "$followup_flag")"
  request_once "$question" "$persona" "$theme" "$request_kind"

  last_theme="$theme"
  last_persona="$persona"

  if [[ ! "$last_status_code" =~ ^2[0-9][0-9]$ ]]; then
    sleep "$(compute_error_backoff_seconds)"
    continue
  fi

  if [[ "$stop_requested" -eq 1 ]]; then
    break
  fi

  if should_trigger_burst "$theme"; then
    burst_sequence=$((burst_sequence + 1))
    burst_size="$(random_int "$BURST_MIN_REQUESTS" "$BURST_MAX_REQUESTS")"

    for ((i = 1; i <= burst_size; i++)); do
      now_epoch="$(date +%s)"
      if [[ "$stop_requested" -eq 1 ]] || [[ "$now_epoch" -ge "$end_epoch" ]]; then
        break
      fi

      question="$(build_question "$theme" "$persona" 1)"
      request_once "$question" "$persona" "$theme" "burst-${burst_sequence}.${i}"

      if [[ "$stop_requested" -eq 1 ]]; then
        break
      fi

      sleep "$(compute_burst_pause_seconds)"
    done
  fi

  if [[ "$stop_requested" -eq 1 ]]; then
    break
  fi

  sleep "$(compute_interval_seconds)"
done
