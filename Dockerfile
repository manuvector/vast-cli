# Dockerfile
FROM huggingface/transformers-pytorch-gpu:latest

# Use bash for RUN steps
SHELL ["/bin/bash", "-lc"]

# Basic CLI utils and editor
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      vim \
      bash-completion \
      less \
      ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Python tools
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir shellm-cli

# Improve readline / input behavior for all users
# - ↑ / ↓ search through history by prefix (like zsh-history-substring-search)
# - case-insensitive completion
# - show all matches without double-tab
# - ctrl+←/→ to move by word (often supported by many terminals as \e[1;5D/C)
RUN cat >/etc/inputrc <<'EOF'
set completion-ignore-case on
set show-all-if-ambiguous on
set mark-symlinked-directories on
# History substring search with arrow keys
"\e[A": history-search-backward
"\e[B": history-search-forward
# Word-wise cursor movement (Ctrl+← / Ctrl+→)
"\e[1;5D": backward-word
"\e[1;5C": forward-word
EOF

# Better bash defaults everywhere
RUN cat >> /etc/bash.bashrc <<'EOF'
# Bigger, smarter history
export HISTSIZE=200000
export HISTFILESIZE=400000
export HISTCONTROL=ignoredups:erasedups
shopt -s histappend cmdhist
# Write new commands to history immediately
PROMPT_COMMAND='history -a; '"$PROMPT_COMMAND"
# Enable bash completion if present
if [ -f /etc/bash_completion ]; then . /etc/bash_completion; fi
# Nice defaults for less
export LESS=-R
EOF

# Workdir
WORKDIR /workspace

# Default shell
CMD ["/bin/bash"]

