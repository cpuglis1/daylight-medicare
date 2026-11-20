#!/bin/zsh
# Start Daylight's dependencies, reload its code, and open the current UI.
umask 077
unsetopt BG_NICE
cd -P -- "${0:A:h}" || exit 1

fail() {
  print -ru2 -- "$*"
  exit 1
}

data="$PWD/infrastructure/daylight-data"
pg_bin="$data/.postgres18/bin"
pg_state="$data/.state"
pg_socket="$pg_state/socket"
pg_port=55485
run_dir="$PWD/alternatives/advisor-first/var/demo-8895"
server_log="$run_dir/server.log"
url='http://localhost:8895/'
check_url='http://127.0.0.1:8895/'

mkdir -p -- "$run_dir" || fail 'Could not create the Daylight runtime directory.'
touch -- "$run_dir/restart.lock" || fail 'Could not create the Daylight restart lock.'
zmodload zsh/system || fail 'Could not load the restart lock support.'
zsystem flock -t 0 "$run_dir/restart.lock" || fail 'Another Daylight restart is already in progress.'

if ! "$pg_bin/pg_isready" -q -h "$pg_socket" -p "$pg_port" -t 2; then
  [[ -r "$pg_state/pgdata/PG_VERSION" && -d "$pg_socket" ]] ||
    fail "The existing Daylight PostgreSQL cluster or socket directory is missing under $pg_state."
  if ! "$pg_bin/pg_ctl" -D "$pg_state/pgdata" status >/dev/null 2>&1; then
    print 'Starting the local Daylight database…'
    "$pg_bin/pg_ctl" -D "$pg_state/pgdata" -l "$pg_state/postgres.log" -w -t 45 \
      -o "-h '' -k ${(q)pg_socket} -p $pg_port" start ||
      fail "PostgreSQL could not start. See $pg_state/postgres.log."
  fi
  for attempt in {1..30}; do
    "$pg_bin/pg_isready" -q -h "$pg_socket" -p "$pg_port" -t 1 && break
    sleep 1
  done
  "$pg_bin/pg_isready" -q -h "$pg_socket" -p "$pg_port" -t 2 ||
    fail "PostgreSQL is not accepting connections on the Daylight socket. See $pg_state/postgres.log."
fi

listener_pid=$(lsof -nP -tiTCP:8895 -sTCP:LISTEN)
if [[ -n "$listener_pid" ]]; then
  [[ "$listener_pid" == <-> ]] || fail 'Multiple processes are listening on port 8895.'
  listener_command=$(ps -ww -o command= -p "$listener_pid")
  [[ "$listener_command" == *'advisor-first/demo_server.py'* &&
     "$listener_command" != *' --fixture'* &&
     "$(lsof -a -p "$listener_pid" -d cwd -Fn)" == *$'\nn'"$PWD" ]] ||
    fail 'Port 8895 is occupied by an unverified process. Daylight left it running.'
  print 'Restarting Daylight on 8895…'
  kill -TERM "$listener_pid" || fail 'Could not stop the current Daylight demo.'
  for attempt in {1..30}; do
    [[ -z "$(lsof -nP -tiTCP:8895 -sTCP:LISTEN)" ]] && break
    sleep 0.5
  done
  [[ -z "$(lsof -nP -tiTCP:8895 -sTCP:LISTEN)" ]] ||
    fail 'Port 8895 did not become free.'
else
  print 'Starting Daylight on 8895…'
fi

nohup "$PWD/Start Daylight Demo.command" </dev/null >>"$server_log" 2>&1 &
demo_pid=$!

http_ok() {
  curl --noproxy '*' --fail --silent --max-time 2 --output /dev/null "$1"
}

for attempt in {1..60}; do
  kill -0 "$demo_pid" 2>/dev/null || fail "Daylight exited during startup. See $server_log."
  if [[ "$(lsof -nP -tiTCP:8895 -sTCP:LISTEN)" == "$demo_pid" ]] &&
     http_ok "$check_url" && http_ok "${check_url}api/status"; then
    print -r -- "$demo_pid" > "$run_dir/server.pid" || fail 'Could not record the Daylight PID.'
    print -r -- "Daylight is ready at $url"
    # Use a fresh navigation and keep the same localhost origin for saved profiles.
    open "${url}?reload=$(/bin/date +%s)-$demo_pid" ||
      fail "Daylight is running. Open $url in your browser."
    exit 0
  fi
  sleep 1
done
kill -TERM "$demo_pid" 2>/dev/null
fail "Daylight did not become ready. See $server_log."
