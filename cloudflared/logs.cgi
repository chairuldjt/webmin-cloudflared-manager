#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
our (%config, %in, %gconfig);
init_config();
ReadParse();

my $cloudflared_bin = $config{'cloudflared'} || "";

# --- Auto-detection ---
my @bin_paths = ("/usr/local/bin/cloudflared", "/usr/bin/cloudflared");
sub find_binary {
    for my $p (@_) { return $p if -x $p; }
    my $w = `which cloudflared 2>&1`;
    chomp($w);
    return $w if $w && -x $w;
    return undef;
}
if (!$cloudflared_bin) { $cloudflared_bin = find_binary(@bin_paths) || "/usr/local/bin/cloudflared"; }

my $lines = $in{'lines'} || 200;
my $filter = $in{'filter'} || "";
my $refresh = $in{'refresh'} || 0;
my $service = $in{'service'} || "cloudflared";

$lines =~ s/[^0-9]//g;
$lines = 200 if !$lines;

&ui_print_header(undef, "Cloudflared Logs", "", undef, 1);

# --- Detect available services ---
my @services = `systemctl list-units --type=service --all 'cloudflared*' --no-legend 2>&1`;
my @service_options;
for my $s (@services) {
    chomp($s);
    next if $s !~ /\S/;
    my @parts = split(/\s+/, $s);
    next if @parts < 1;
    my $name = $parts[0];
    $name =~ s/\.service$//;
    my $label = $name;
    $label =~ s/^cloudflared-?//;
    $label = "Main Service" if $label eq "cloudflared" || $label eq "";
    push @service_options, [ $name, "$label ($name)" ];
}

# If no services found, add default option
unless (@service_options) {
    push @service_options, [ "cloudflared", "Main Service (cloudflared)" ];
}

# --- Log options form ---
print &ui_form_start("logs.cgi", "get");
print &ui_table_start({ title => "Log Viewer Options", width => "80%" });

print &ui_table_row("Service",
    &ui_radio_select("service", $service, \@service_options)
);

print &ui_table_row("Lines",
    &ui_textbox("lines", $lines, 6) . " " .
    &ui_submit("View")
);

print &ui_table_row("Filter (grep)",
    &ui_textbox("filter", $filter, 30) . " " .
    &ui_submit("Filter")
);

if ($refresh) {
    print &ui_table_row("Auto-refresh",
        "<span style='color:green;'><b>Enabled (every 30s)</b></span> &nbsp; " .
        &ui_link("logs.cgi?service=$service&lines=$lines&filter=$filter", "Disable")
    );
} else {
    print &ui_table_row("Auto-refresh",
        &ui_link("logs.cgi?service=$service&lines=$lines&filter=$filter&refresh=1", "Enable Auto-refresh (30s)")
    );
}

print &ui_table_end();
print &ui_form_end();

print &ui_hr();

# --- Fetch logs ---
my $cmd = "journalctl -u $service -n $lines --no-pager 2>&1";

if ($filter) {
    my $safe_filter = quotemeta($filter);
    $cmd .= " | grep -i $safe_filter";
}

my $service_label = $service;
$service_label =~ s/^cloudflared-?//;
$service_label = "Main Service" if $service_label eq "cloudflared" || $service_label eq "";

print "<div style='margin-bottom:8px;'><b>Service:</b> $service &nbsp;|&nbsp; <b>Lines:</b> $lines" .
      ($filter ? " &nbsp;|&nbsp; <b>Filter:</b> '$filter'" : "") . "</div>";

print "<pre style='background:#1a1a2e; color:#e0e0e0; padding:15px; border-radius:4px; overflow:auto; max-height:600px; font-size:12px; line-height:1.4; white-space:pre-wrap;'>";

my $logs = `$cmd`;

if (!$logs && $service ne "cloudflared") {
    $logs = `journalctl -u cloudflared -n $lines --no-pager 2>&1`;
    if ($logs) {
        print "<!-- No logs for $service, showing main cloudflared logs -->\n";
    }
}

if ($logs) {
    print &escape_html($logs);
} else {
    print "No logs available. The service may not exist or has not produced any logs yet.\n";
    print "Try running: journalctl -u $service";
}

print "</pre>";

# --- Refresh script ---
if ($refresh) {
    print &ui_hr();
    print "<script>
        setTimeout(function() {
            window.location.href = 'logs.cgi?service=$service&lines=$lines&filter=$filter&refresh=1';
        }, 30000);
    </script>
    <noscript>
        <div style='padding:10px; background:#fff3cd; border:1px solid #ffc107; margin:10px 0;'>
            Enable JavaScript for auto-refresh.
        </div>
    </noscript>
    ";
}

&ui_print_footer("index.cgi", "Back to Manager");
