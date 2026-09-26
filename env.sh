# Cargar antes de compilar:  source env.sh
# macOS: GNU Make 4 (brew "make") y el Python de brew antes que pyenv.
# Funciona con brew en /opt/homebrew (Apple Silicon) o /usr/local (Intel).
# En Ubuntu no hace falta: make 4 y python3 del sistema ya sirven.
if [ "$(uname)" = "Darwin" ]; then
  _brew="$(command -v brew || ls /opt/homebrew/bin/brew /usr/local/bin/brew 2>/dev/null | head -1)"
  if [ -n "$_brew" ]; then
    _prefix="$("$_brew" --prefix)"
    export PATH="$_prefix/opt/make/libexec/gnubin:$_prefix/bin:$PATH"
  fi
  unset _brew _prefix
fi
