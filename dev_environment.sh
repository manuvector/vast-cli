et -euo pipefail

echo "==> Installing vim + shellm-cli, and setting up history search..."

# --- package install (vim) ---
if command -v apt-get >/dev/null 2>&1; then
	  sudo apt-get update -y
	    sudo apt-get install -y vim
    elif command -v dnf >/dev/null 2>&1; then
	      sudo dnf install -y vim
      elif command -v yum >/dev/null 2>&1; then
	        sudo yum install -y vim
	elif command -v apk >/dev/null 2>&1; then
		  sudo apk add --no-cache vim
	  elif command -v pacman >/dev/null 2>&1; then
		    sudo pacman -Sy --noconfirm vim
	    else
		      echo "!! No supported package manager found, please install vim manually."
fi

# --- shellm-cli via pip ---
if command -v python3 >/dev/null 2>&1; then
	  python3 -m pip install --user --upgrade pip shellm-cli
  else
	    echo "!! python3 not found, skipping shellm-cli install."
fi

# --- inputrc for history search ---
cat > "${HOME}/.inputrc" <<'EOF'
# Up / Down arrow search history by current prefix
"\e[A": history-search-backward
"\e[B": history-search-forward
EOF

# --- ensure bashrc loads it ---
if ! grep -q 'bind -f ~/.inputrc' "${HOME}/.bashrc" 2>/dev/null; then
	  echo 'bind -f ~/.inputrc' >> "${HOME}/.bashrc"
fi

echo
echo "✅ Done!"
echo "• vim installed"
echo "• shellm-cli installed (pip user mode)"
echo "• ~/.inputrc created for prefix-based history search (↑ / ↓)"
echo "• ~/.bashrc updated with 'bind -f ~/.inputrc'"
echo
echo "➡️  Open a new shell or run: source ~/.bashrc"
