# Titanium Privacy Policy
*v1.0.1, updated 20/01/25 (DD/MM/YY)*\
This document explains how Titanium treats your data. **Please note that this Privacy Policy only applies to the official main Titanium bot instance. When using other Titanium instances, please refer to their own Privacy Policies.**

## Definitions
- *"bot"* - an app developed for Discord.
- *"Titanium", "Titanium Bot", "the bot"* - the Titanium Discord bot.
- *"we"* - Restart Software.
- *"guild"* - a Discord server. Not to be confused with the bot hosting server (labelled *"the server"*).

## Data we collect
When using certain Titanium features, we may need to collect and process some data. Titanium accesses this data using the Discord API; all of the data is publicly accessible. The data collected may include but is not limited to:
- User Information *(incl. IDs, profile picture URLs)*
- User Permissions in guilds
- Guild Information *(incl. guild members)*
- Message Info *(incl. IDs)*

This information is not collected to be stored, unless explicitly specified for one of the following features:
### **Edit History Feature**
When the edit history feature is enabled, the following information will be collected and stored:
- Guild ID
- Original Message content *(if message has been edited and feature is enabled)*
- Content of each edit *(if message has been edited and feature is enabled)*

> [!NOTE]
> This data is deleted if the bot leaves the guild or if a guild admin disables the feature.

These edits can only be viewed by guild members that have permission to use the feature. This permission can be granted by the guild owner. This permission is granted from within Discord's command settings. Please contact the guild's owner to find out if the feature is enabled and who has access to it. When the edit feature is disabled in the guild, this feature will not collect any information.
### **Fireboard Feature**
When the fireboard feature is enabled, Titanium will need to collect and store the following information:
- Guild ID
- Message ID to be added to the fireboard
- Fireboard message ID
- Number of selected reactions on the message

> [!NOTE]
> This data is deleted if the message drops below the reaction requirement or if a guild admin disables the feature. Message content will **not** be stored by this feature.

Titanium will also store the following user-defined settings:
- Target amount of reactions
- Selected reaction
- Fireboard channel ID
- Whether to ignore bot messages
- Corresponding guild ID

> [!NOTE]
> This data is deleted if the bot leaves the guild or if a guild admin disables the feature.
### **Leaderboard Feature**
When the guild leaderboard feature is enabled, Titanium will need to collect and store the following information:
- Guild ID
- Your User ID
- The amount of messages you send
- The amount of words you have sent
- The amount of attachments you have sent

To collect this information, Titanium will need to temporarily store the content of messages in RAM. Once the length of the message has been processed, it will be discarded. The content of the message will not be permanently saved in any place, and can not be collected while the processing is taking in place.

> [!NOTE]
> This data is deleted if the bot leaves the guild or if a guild admin disables the feature.

#### Opting Out
You can optionally opt out of leaderboard data collection. To do this, use the `/leaderboard opt-out` command. When you opt out, your user ID will be stored in an SQL table. If your user ID is in that table, no information will be processed or stored for the leaderboard. in any servers that have the Titanium leaderboard enabled. If you have opted out previously and want to opt back in, use the `/leaderboard opt-in` command.
### **Tags Feature**
When you create tags with Titanium, the following information will be stored:
- Name of the tag
- Content of the tag
- Creator's User ID

> [!NOTE]
>This data is removed if you delete the tag.
### **Music Features**
When you use Titanium's Song URL feature, Titanium will store some anonymous information in a cache to speed up future uses of the command. The following information will be stored:
- User provided link
- User provided link's platform

> [!NOTE]
>Each cache entry will expire after 30 days.
### **Image Features**
When using Titanium's image processing features, the image will be temporarily downloaded to our server so it can be processed. Once the file has been processed, the original copy and processed copy will be deleted from our server.

## Data Retention
Unless otherwise specified in feature-specific sections, we retain data only for as long as necessary to provide our bot's services. When data is no longer needed, it is deleted from our server.

## Bot Usage Collection
When you run a Titanium command or use a Titanium context menu item, we collect the following information:
- Command / context menu item used
- Time the command / context menu item was ran at
- Guild the command / context menu item was ran in *(not collected if the bot is not in the guild)*
- User that ran the command / context menu item

We do not collect any arguments that you provide (URLs, attachments, etc).

## Processing Location
Titanium is hosted in the United Kingdom. By using Titanium, you agree to your data being processed according to this privacy policy, and local laws / regulations in the United Kingdom.

## Third Party Data Sharing
We do not share any data with third parties, apart from Discord for core functionality of the bot or when required by law. Discord may collect some data during regular usage of their service, such as commands ran, message content and attachments sent. Please refer to their [privacy policy](https://discord.com/privacy) for more information.

## Your Rights
You have the right to:
- Request access to your data (by contacting us, see contact us section)
- Request deletion of your data (using opt-out commands)
- Opt-out of data collection (using opt-out commands)

## Backups
We take daily backups of our server to ensure that we can restore data if a data loss event occurs. We keep backups from the past 3 days using Proxmox container snapshots.

## Data Breach Notifications
We ensure that we do not collect any information that may impact you if a data breach occurs. However, if we believe a data breach has occurred and data may have been accessed, we will do the following:
- A public announcement informing users that the breach has occurred
- Attempt to contact affected users individually with more info about the data that was accessed

## Policy Updates
We may make changes to this policy over time. If a major change is made to the privacy policy, you will be notified when you next run a command with the bot. We will also make an announcement over public channels.

## Contact Us
If you wish to contact us about a privacy related concern (policy enquiry, data access request, etc.), please use the following email address:
`privacy@titaniumbot.me`

We will attempt to get back to you ASAP regarding your concern.

**Only use this email for privacy related concerns and enquiries. Non privacy related emails will be ignored.**
