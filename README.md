# ShifuBot

<img src="https://raw.githubusercontent.com/AceHanded/ShifuBot/main/Images/icon.png" alt="shifuboticon" width="250"/>


## Description

Multifunctional Discord bot implementation using Python, with emphasis on music commands.

ShifuBot has come a long way in the few years that it has been in development, and although still not perfect, the current release is "stable enough". I will keep updating the bot irregularly when I can think of improvements, when I have time and when I feel like it.

**Note:** I will most likely not be releasing the bot itself for public use, at least not any time soon. However, I have included template files for the project, so you can run your own Discord bot using ShifuBot's code as a base. Simply remove the `.template` suffix from the `.env` file and add the values of the API keys / tokens to match your own, and you should be good to go.


## Changelog

<details>
  <summary>v1.0.9</summary>
    
    - Added voice commands.
    * Enabled by muting and unmuting the microphone, after which, the bot listens to speech for 5 seconds.
    * Supports English and Finnish.
    * Current commands are `play | toista`, `skip | seuraava`, `pause | pysäytä` and `disconnect | painu vittuun`.

    - Re-added the `settings` command, which allows toggling of speech recognition, as well as its language.

    - Modified the `play` command's main embed to dynamically change when the queue changes.

    - Fixed appearance of duplicates in the suggested tracks in the `play` command.
    
    - Cleaned up the `lyrics` command due to changes in the `lyricsgenius` library.
</details>
<details>
    <summary>v1.0.8</summary>
    
    - Fixed an error with the select menu, when a song was not found.

    - Fixed an error with the `lyrics` command, when the lyrics were too long for Discord.

    - Fixed an issue that caused the buttons of the `play` command to not be cleared properly when the bot disconnects.
</details>
<details>
    <summary>v1.0.7</summary>
    
    - Fixed an issue that caused the `insert` parameter of the `play` command to not function.

    - Fixed an issue that caused the current song to start over when a song was added to the queue, when the current one was paused.
</details>
<details>
    <summary>v1.0.6</summary>
    
    - Rewrote everything.
      * More concise, yet performant code.
      * Changed the elapsed duration handling from a counter-based implementation to one using the `time` library.
      * Changed the way the `nightcore` filter works.
      * Fixed remaining concurrency issues.

    - Added a select menu for suggested tracks in the `play` command.

    - Added an `autoplay` command that automatically adds and plays songs in queue.

    - Added parameter `previous` to the `view` command, which makes it possible to view the songs in previous queue.

    - Added parameter `instant` to the `replay` command, which makes it possible to replay the given song instantly.

    - Added parameter `from_` to the `leaderboard` command, which makes it possible to specify the starting position of the leaderboard display.

    - Removed support for custom languages (at least for now).

    - Removed the `settings` and `thought` commands.
</details>
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
