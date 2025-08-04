# ShifuBot

[![License](https://img.shields.io/github/license/AceHanded/ShifuBot?style=for-the-badge)](https://github.com/AceHanded/ShifuBot/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/downloads/)
[![BuyMeACoffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/acehand)

<img src="https://raw.githubusercontent.com/AceHanded/ShifuBot/main/Images/icon.png" alt="shifuboticon" width="250"/> \

Multifunctional Discord bot implementation using Python, with emphasis on music commands.

> [!NOTE]
> This repository contains the source code of the bot, so that you may use it as a template for your own implementation.


## Getting started

First, you should fork this repository to create a copy of it on your own account.

Next, you can clone the repository to your local machine with the following command, where "{your_username}" is your GitHub username.

```bash
git clone https://github.com/{your_username}/ShifuBot.git
```

> [!TIP]
> Forking allows you to track changes independently. Use it!

Alternatively, you can clone the original repository, or download the source code of the latest release straight from the `Releases` section.


## Prerequisites

### Requirements

Python 3.11+ is recommended to ensure compatibility.

The required packages can be installed from the `requirements.txt` file with the following command.

```bash
pip install -r requirements.txt
```

### Environment variables

A `.env` file template is included and you just have to fill in the variable values. Afterwards, you can remove the `.template` suffix from the filename. \
If you do not need certain variables for your own implementation, make sure your code handles their absence appropriately.


## Usage

Once everything is set up, the bot can be ran with the following command.

```bash
python main.py
```

For information about individual commands of the bot, use its `/help` command.