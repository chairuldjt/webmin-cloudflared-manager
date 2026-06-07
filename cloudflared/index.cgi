#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
init_config();
ReadParse();

my $status = `systemctl is-active cloudflared 2>&1`;
chomp($status);

&ui_print_header(undef, "Cloudflared Manager", "", undef, 1);

# Status box
print &ui_table_start("Service Information", "width=60%");
print &ui_table_row("Cloudflared Status", "<b style='color:" . 
    ($status eq "active" ? "green'>Active" : "red'>Inactive") . "</b>");
print &ui_table_end();

# Action buttons
print "<div style='margin:20px 0; text-align:center;'>";
print "<a class='ui_button' style='margin:5px;' href='index.cgi?action=start'>u{25B6} Start</a>";
print "<a class='ui_button' style='margin:5px;' href='index.cgi?action=stop'>u{23F9} Stop</a>";
print "<a class='ui_button' style='margin:5px;' href='index.cgi?action=restart'>u{1F504} Restart</a>";
print "<a class='ui_button' style='margin:5px;' href='logs.cgi'>u{1F4CB} View Logs</a>";
print "<a class='ui_button' style='margin:5px;' href='config.cgi'>u{2699} Edit Config</a>";
print "</div>";

# Action handling
if ($in{'action'}) {
    print "<div style='margin-top:20px; padding:10px; border:1px solid #ccc; background:#f9f9f9;'>";
    if ($in{'action'} eq "start") {
        system("systemctl start cloudflared");
        print "<b style='color:green;'>u{2705} Cloudflared started</b>";
    } elsif ($in{'action'} eq "stop") {
        system("systemctl stop cloudflared");
        print "<b style='color:red;'>u{23F9} Cloudflared stopped</b>";
    } elsif ($in{'action'} eq "restart") {
        system("systemctl restart cloudflared");
        print "<b style='color:blue;'>u{1F504} Cloudflared restarted</b>";
    }
    print "</div>";
}

&ui_print_footer("/", "Back to Webmin");

