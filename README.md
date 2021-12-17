# Ambiguous PNG Packer

Craft PNG files that appear completely different in Apple software

For context: https://www.da.vidbuchanan.co.uk/widgets/pngdiff/

## Sample output:

![sample image](/samples/mac_vs_ibm_output.png)

If you're viewing this via Apple software (e.g. Safari) you should see an image of a mac, and on other non-Apple software, you should see an IBM PC. (Note: If you're in Safari and still seeing the IBM PC, hit refresh a few times...)

As a bonus, here's a race condition I found in desktop macOS Safari:

![race condition](/samples/race_condition.png)

You should see a slightly different image on each page refresh!

Here's a "live" version, which self-refreshes on each frame: https://www.da.vidbuchanan.co.uk/widgets/pngdiff/race.html
