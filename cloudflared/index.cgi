#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
our (%config, %in, %gconfig);
init_config();
ReadParse();

my $cloudflared_bin = $config{'cloudflared'} || "";

my @bin_paths = ("/usr/local/bin/cloudflared", "/usr/bin/cloudflared");
sub find_binary {
    for my $p (@_) { return $p if -x $p; }
    my $w = `which cloudflared 2>&1`; chomp($w);
    return $w if $w && -x $w; return undef;
}
if (!$cloudflared_bin) { $cloudflared_bin = find_binary(@bin_paths) || "/usr/local/bin/cloudflared"; }

my $bin_exists = -x $cloudflared_bin;
sub btn { my ($u, $t) = @_; return "<a class='ui_button' href='$u'>$t</a>" }

sub tunnel_list {
    my $out = `$cloudflared_bin tunnel list 2>&1`;
    return undef if $?;
    my @t; my $h = 0;
    for (split(/\n/, $out)) {
        if (/^ID\s/) { $h = 1; next }
        next if !$h || /^\-+$/ || !/\S/;
        if (/^([\w\-]+)\s+(\S+)\s+(\S.+)$/) { push @t, { id=>$1, name=>$2, status=>$3 } }
    }
    return \@t;
}

sub tunnel_sysd {
    my @s = `systemctl list-units --type=service --all 'cloudflared*' --no-legend 2>&1`;
    my @t;
    for (@s) { chomp; next if !/\S/; my @p = split(/\s+/); next if @p < 4;
        my $n = $p[0]; $n =~ s/\.service$//;
        push @t, { id=>$p[0], name=>($n ne "cloudflared" ? $n : "cloudflared (main)"), raw_name=>$n, status=>($p[3] eq "running" ? "active" : "inactive"), source=>"systemd" } }
    return \@t;
}

sub tunnel_cfg {
    return [] if !-d "/etc/cloudflared";
    my @t; opendir(my $dh, "/etc/cloudflared");
    for (readdir($dh)) { next if !/\.ya?ml$/; my $f = "$_"; my $n = $f; $n =~ s/\.ya?ml$//;
        my $s = `systemctl is-active cloudflared-tunnel-$n 2>&1`; chomp($s);
        $s = "unknown" if $s !~ /^(active|inactive|failed)$/;
        push @t, { id=>"/etc/cloudflared/$f", name=>$n, raw_name=>$n, status=>$s, source=>"config" } }
    closedir($dh); return \@t;
}

sub msg {
    my ($t, $text) = @_;
    my ($bg, $fg, $bd) = $t eq "ok" ? ("#d4edda","#155724","#c3e6cb") : ("#f8d7da","#721c24","#f5c6cb");
    print "<div style='margin:15px 0; padding:10px; background:$bg; color:$fg; border:1px solid $bd; border-radius:4px;'>$text</div>";
}

my $action = $in{'action'} || '';
my $confirm = $in{'confirm'} || '';
my $tn = $in{'tunnel'} || '';

if ($action && $confirm eq "yes") {
    &ui_print_header(undef, "Operation Result", "", undef, 1);
    if ($action eq "start_service")   { my $r = `systemctl start cloudflared 2>&1`;   msg($? ? "err" : "ok", $? ? $r : "Cloudflared service started.") }
    elsif ($action eq "stop_service")    { my $r = `systemctl stop cloudflared 2>&1`;    msg($? ? "err" : "ok", $? ? $r : "Cloudflared service stopped.") }
    elsif ($action eq "restart_service") { my $r = `systemctl restart cloudflared 2>&1`; msg($? ? "err" : "ok", $? ? $r : "Cloudflared service restarted.") }
    elsif ($action eq "start_tunnel" && $tn) {
        my $r = `systemctl start cloudflared-tunnel-$tn 2>&1`;
        $? ? msg("err", "No systemd service found. Tunnel started in background.") : msg("ok", "Tunnel '$tn' started.")
    }
    elsif ($action eq "stop_tunnel" && $tn) {
        my $r = `systemctl stop cloudflared-tunnel-$tn 2>&1`;
        $? ? do { my $r2 = `pkill -f "cloudflared tunnel run $tn" 2>&1`; msg($? ? "err" : "ok", $? ? $r2 : "Tunnel '$tn' stopped.") } : msg("ok", "Tunnel '$tn' stopped.")
    }
    elsif ($action eq "restart_tunnel" && $tn) { my $r = `systemctl restart cloudflared-tunnel-$tn 2>&1`; msg($? ? "err" : "ok", $? ? $r : "Tunnel '$tn' restarted.") }
    elsif ($action eq "delete_tunnel" && $tn)   { my $r = `$cloudflared_bin tunnel delete $tn 2>&1`; msg($? ? "err" : "ok", $? ? $r : "Tunnel '$tn' deleted.") }
    print &ui_hr(); print btn("index.cgi", "Back to Dashboard");
    &ui_print_footer("index.cgi", "Back"); exit;
}

if ($action && !$confirm) {
    my %ct = ( start_service=>"Start Main Service", stop_service=>"Stop Main Service", restart_service=>"Restart Main Service", start_tunnel=>"Start Tunnel", stop_tunnel=>"Stop Tunnel", restart_tunnel=>"Restart Tunnel", delete_tunnel=>"Delete Tunnel" );
    &ui_print_header(undef, $ct{$action} || ucfirst($action), "", undef, 1);
    if ($action eq "delete_tunnel") {
        &ui_confirm("Are you sure you want to permanently delete tunnel '<b>$tn</b>'? This cannot be undone.", "index.cgi?action=$action&tunnel=$tn&confirm=yes", "index.cgi", "Yes, Delete", "Cancel")
    } else {
        my $v = $action =~ /^start/ ? "start" : ($action =~ /^stop/ ? "stop" : "restart");
        my $d = $tn ? "tunnel '$tn'" : "main Cloudflared service";
        &ui_confirm("Are you sure you want to <b>$v</b> $d?", "index.cgi?action=$action&tunnel=$tn&confirm=yes", "index.cgi", "Yes, $v", "Cancel")
    }
    &ui_print_footer("index.cgi", "Back"); exit;
}

my $ta = $bin_exists ? tunnel_list() : undef;
my $ts = $bin_exists ? tunnel_sysd() : [];
my $tc = tunnel_cfg();

&ui_print_header(undef, "Cloudflared Manager", "", undef, 1);

my $ms = `systemctl is-active cloudflared 2>&1`; chomp($ms);
my $mc = $ms eq "active" ? "ui_green" : "ui_red";
my $ml = $ms eq "active" ? "Active" : "Inactive";
my $ver = ""; if ($ms eq "active") { $ver = `$cloudflared_bin --version 2>&1`; chomp($ver) }

print &ui_table_start("Cloudflared Overview", "width=75%");
print &ui_table_row("Cloudflared Binary", $cloudflared_bin . ($bin_exists ? " <span style='color:green;font-size:10px;'>(found)</span>" : " <span style='color:red;font-size:10px;'>(not found)</span>"));
print &ui_table_row("Main Service Status", "<span class='$mc'><b>$ml</b></span>");
print &ui_table_row("Version", $ver) if $ver;
print &ui_table_end();

print &ui_hr();
print &ui_form_start("index.cgi", "get");
print &ui_table_start("Main Service Actions", "width=75%");
print &ui_table_row("Action", &ui_select("action", "", [ ["start_service","Start Service"], ["stop_service","Stop Service"], ["restart_service","Restart Service"] ]) . " " . &ui_submit("Execute"));
print &ui_table_end();
print &ui_form_end();

print &ui_hr();
print "<h3>Tunnels</h3>\n";

my @all; my %seen;
if ($ta && @$ta) { for (@$ta) { $seen{$_->{name}}=1; push @all, $_ } }
for (@$ts) { next if $seen{$_->{raw_name}}; $seen{$_->{raw_name}}=1; push @all, $_ }
for (@$tc) { next if $seen{$_->{raw_name}}; $seen{$_->{raw_name}}=1; push @all, $_ }

if (@all) {
    for (@all) { if ($_->{source} ne "systemd") { my $s = `systemctl is-active cloudflared-tunnel-$_->{raw_name} 2>&1`; chomp($s); $_->{status} = $s if $s =~ /^(active|inactive|failed)$/ } }
    print &ui_table_start("Configured Tunnels", "width=95%");
    &ui_columns_start(["Tunnel Name","Status","Source","Actions"], ["30%","15%","15%","40%"]);
    for my $t (@all) {
        my $sc = $t->{status} eq "active" ? "ui_green" : ($t->{status} eq "inactive" ? "ui_red" : "");
        my $ac = ($t->{status} eq "active" ? btn("index.cgi?action=stop_tunnel&tunnel=$t->{raw_name}","Stop").btn("index.cgi?action=restart_tunnel&tunnel=$t->{raw_name}","Restart") : btn("index.cgi?action=start_tunnel&tunnel=$t->{raw_name}","Start"));
        $ac .= btn("config.cgi?tunnel=$t->{raw_name}","Config");
        $ac .= btn("logs.cgi?service=cloudflared-tunnel-$t->{raw_name}","Logs");
        $ac .= btn("index.cgi?action=delete_tunnel&tunnel=$t->{raw_name}","Delete");
        &ui_columns_row([ $t->{name}, "<span class='$sc'><b>".($t->{status}||"unknown")."</b></span>", $t->{source}||"auto", $ac ])
    }
    &ui_columns_end(); print &ui_table_end()
} else {
    print "<div style='padding:10px; background:#f8d7da; color:#721c24; border:1px solid #f5c6cb; border-radius:4px; margin:15px 0;'>No tunnels found. Configure one in Settings or via cloudflared CLI.</div>"
}

print &ui_hr();
print &ui_table_start("Management", "width=50%");
print &ui_table_row("Quick Links", btn("config.cgi","Settings & Config Editor") . " " . btn("logs.cgi","View Logs"));
print &ui_table_end();

&ui_print_footer("/", "Back to Webmin");
