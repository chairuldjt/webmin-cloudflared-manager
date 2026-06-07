#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
init_config();

&ui_print_header(undef, "Cloudflared Logs", "", undef, 1);

print "<pre>";
my $logs = `journalctl -u cloudflared -n 200 --no-pager 2>&1`;
print $logs;
print "</pre>";

&ui_print_footer("index.cgi", "Back");
