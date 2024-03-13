# ShifuBot

<img src="https://raw.githubusercontent.com/AceHanded/ShifuBot/main/Images/icon.png" alt="shifuboticon" width="250"/>


## Description

Multifunctional Discord bot implementation using Python, with emphasis on music commands.

ShifuBot has come a long way in the few years that it has been in development, and although still not perfect, the current release is "stable enough". I will keep updating the bot irregularly when I can think of improvements, when I have time and when I feel like it.

**Note:** I will most likely not be releasing the bot itself for public use, at least not any time soon. However, I have included template files for the project, so you can run your own Discord bot using ShifuBot's code as a base. Simply remove the `.template` suffix from the `.env` file and add the values of the API keys / tokens to match your own, and you should be good to go.


## Changelog

<details>
    <summary>v1.0.5</summary>
    
    - Fixed an issue that caused the `seek` and `filter` commands to work extremely slowly, especially with longer songs.
</details>
<details>
    <summary>v1.0.4</summary>
    
    - Fixed an issue that caused the music-related properties of a guild to be saved to dictionaries, even if an error occurs.
</details>
<details>
    <summary>v1.0.3</summary>
    
    - Fixed cleanup not being initialized properly after a forced disconnect.
      * Also added a message for when the bot is disconnected this way.
</details>
<details>
    <summary>v1.0.2</summary>
    
    - Added support for custom languages.
    
    - Added a `settings.json` file for modifying guild specific settings.
      * Also added a `settings` command for changing the language.

    - Improved the `loop` command's `queue` mode.

    - The `pause` and `loop` buttons of the `play` command now change color based on their state.
</details>
<details>
    <summary>v1.0.1</summary>
    
    - Added a `loop` button to the `play` command's main embed, which cycles between the different loop-modes.

      * Also added information to the main embed about the amount of times a single song has been looped.

    - Added error messages.

      * For the `play` command, when there are no search results found for the given query, as well as for a BrokenPipeError.

      * For the `generate` command, when the OpenAI quota has been exceeded.

    - Added parameter `to` to the `leaderboard` command, and increased default amount of shown users from 5 to 10.

    - Reduced the amount of "message clutter" that the commands `blackjack` and `brawl` produce.

    - The command `skip` now sets the loop-mode to `Disabled`, making it possible to actually skip songs that are being looped.
    
    - The command `play` now correctly removes the buttons from its main embed even after an hour has passed.
</details>
<details>
    <summary>v1.0.0</summary>
    
    - Initial project release.
</details>
