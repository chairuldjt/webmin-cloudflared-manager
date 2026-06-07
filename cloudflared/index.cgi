#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
our (%config, %in, %gconfig);
init_config();
ReadParse();

my $cloudflared_bin = $config{'cloudflared'} || "";

my @bin_paths = (
    "/usr/local/bin/cloudflared",
    "/usr/bin/cloudflared",
);

sub find_binary {
    for my $p (@_) { return $p if -x $p; }
    my $w = `which cloudflared 2>&1`;
    chomp($w);
    return $w if $w && -x $w;
    return undef;
}

if (!$cloudflared_bin) { $cloudflared_bin = find_binary(@bin_paths) || "/usr/local/bin/cloudflared"; }

my $bin_exists = -x $cloudflared_bin;

sub get_tunnels_from_list {
    my $out = `$cloudflared_bin tunnel list 2>&1`;
    return undef if $?;
    my @tunnels;
    my @lines = split(/\n/, $out);
    my $header_found = 0;
    for my $line (@lines) {
        if ($line =~ /^ID\s/) { $header_found = 1; next; }
        next if !$header_found || $line =~ /^\-+$/ || $line !~ /\S/;
        if ($line =~ /^([\w\-]+)\s+(\S+)\s+(\S.+)$/) {
            push @tunnels, { id => $1, name => $2, status => $3 };
        }
    }
    return \@tunnels;
}

sub get_tunnels_from_systemd {
    my @services = `systemctl list-units --type=service --all 'cloudflared*' --no-legend 2>&1`;
    my @tunnels;
    for my $s (@services) {
        chomp($s);
        next if $s !~ /\S/;
        my @parts = split(/\s+/, $s);
        next if @parts < 4;
        my $service = $parts[0];
        my $sub = $parts[3];
        my $name = $service;
        $name =~ s/\.service$//;
        my $is_tunnel = ($name ne "cloudflared");
        my $display_name = $is_tunnel ? $name : "cloudflared (main)";
        my $running = ($sub eq "running" ? "active" : "inactive");
        push @tunnels, {
            id => $service,
            name => $display_name,
            raw_name => $name,
            status => $running,
            source => "systemd",
        };
    }
    return \@tunnels;
}

sub get_tunnels_from_configs {
    my $conf_dir = "/etc/cloudflared";
    return [] if !-d $conf_dir;
    my @configs;
    opendir(my $dh, $conf_dir);
    while (my $f = readdir($dh)) {
        next if $f !~ /\.ya?ml$/;
        my $full = "$conf_dir/$f";
        next if !-f $full;
        my $name = $f;
        $name =~ s/\.ya?ml$//;
        my $running = `systemctl is-active cloudflared-tunnel-$name 2>&1`;
        chomp($running);
        if ($running !~ /^(active|inactive|failed)$/) { $running = "unknown"; }
        push @configs, {
            id => $full,
            name => $name,
            raw_name => $name,
            status => $running,
            source => "config",
        };
    }
    closedir($dh);
    return \@configs;
}

sub show_message {
    my ($type, $text) = @_;
    my $color = $type eq "success" ? "#d4edda" : "#f8d7da";
    my $text_color = $type eq "success" ? "#155724" : "#721c24";
    my $border = $type eq "success" ? "#c3e6cb" : "#f5c6cb";
    print "<div style='margin:15px 0; padding:10px; background:$color; color:$text_color; border:1px solid $border; border-radius:4px;'>";
    print $text;
    print "</div>";
}

my $action = $in{'action'} || '';
my $confirm = $in{'confirm'} || '';
my $tunnel_name = $in{'tunnel'} || '';

if ($action && $confirm eq "yes") {
    &ui_print_header(undef, "Operation Result", "", undef, 1);

    if ($action eq "start_service") {
        my $r = `systemctl start cloudflared 2>&1`;
        show_message($? == 0 ? "success" : "error", $? == 0 ? "Cloudflared service started." : $r);
    } elsif ($action eq "stop_service") {
        my $r = `systemctl stop cloudflared 2>&1`;
        show_message($? == 0 ? "success" : "error", $? == 0 ? "Cloudflared service stopped." : $r);
    } elsif ($action eq "restart_service") {
        my $r = `systemctl restart cloudflared 2>&1`;
        show_message($? == 0 ? "success" : "error", $? == 0 ? "Cloudflared service restarted." : $r);
    } elsif ($action eq "start_tunnel" && $tunnel_name) {
        my $r = `systemctl start cloudflared-tunnel-$tunnel_name 2>&1`;
        if ($?) {
            $r = `$cloudflared_bin tunnel run $tunnel_name --no-autoupdate 2>&1 &`;
            show_message("error", "No systemd service found. Tunnel started in background.");
        } else {
            show_message("success", "Tunnel '$tunnel_name' started.");
        }
    } elsif ($action eq "stop_tunnel" && $tunnel_name) {
        my $r = `systemctl stop cloudflared-tunnel-$tunnel_name 2>&1`;
        if ($?) {
            $r = `pkill -f "cloudflared tunnel run $tunnel_name" 2>&1`;
            show_message($? == 0 ? "success" : "error", $? == 0 ? "Tunnel '$tunnel_name' stopped." : $r);
        } else {
            show_message("success", "Tunnel '$tunnel_name' stopped.");
        }
    } elsif ($action eq "restart_tunnel" && $tunnel_name) {
        my $r = `systemctl restart cloudflared-tunnel-$tunnel_name 2>&1`;
        show_message($? == 0 ? "success" : "error", $? == 0 ? "Tunnel '$tunnel_name' restarted." : $r);
    } elsif ($action eq "delete_tunnel" && $tunnel_name) {
        my $r = `$cloudflared_bin tunnel delete $tunnel_name 2>&1`;
        show_message($? == 0 ? "success" : "error", $? == 0 ? "Tunnel '$tunnel_name' deleted." : $r);
    }

    print &ui_hr();
    print "<a class='ui_button' href='index.cgi'>Back to Dashboard</a>";
    &ui_print_footer("index.cgi", "Back");
    exit;
}

if ($action && !$confirm) {
    my %confirm_titles = (
        start_service => "Start Main Service",
        stop_service => "Stop Main Service",
        restart_service => "Restart Main Service",
        start_tunnel => "Start Tunnel",
        stop_tunnel => "Stop Tunnel",
        restart_tunnel => "Restart Tunnel",
        delete_tunnel => "Delete Tunnel",
    );

    my $title = $confirm_titles{$action} || ucfirst($action);
    my $desc = $tunnel_name ? "tunnel '$tunnel_name'" : "main Cloudflared service";

    if ($action eq "delete_tunnel") {
        &ui_print_header(undef, $title, "", undef, 1);
        &ui_confirm("Are you sure you want to permanently delete tunnel '<b>$tunnel_name</b>'? This cannot be undone.",
                     "index.cgi?action=$action&tunnel=$tunnel_name&confirm=yes", "index.cgi",
                     "Yes, Delete", "Cancel");
    } else {
        my $verb = $action =~ /^start/ ? "start" : ($action =~ /^stop/ ? "stop" : "restart");
        &ui_print_header(undef, $title, "", undef, 1);
        &ui_confirm("Are you sure you want to <b>$verb</b> $desc?",
                     "index.cgi?action=$action&tunnel=$tunnel_name&confirm=yes", "index.cgi",
                     "Yes, $verb", "Cancel");
    }

    &ui_print_footer("index.cgi", "Back");
    exit;
}

my $tunnels_api = $bin_exists ? get_tunnels_from_list() : undef;
my $tunnels_sys = $bin_exists ? get_tunnels_from_systemd() : [];
my $tunnels_cfg = get_tunnels_from_configs();

&ui_print_header(undef, "Cloudflared Manager", "", undef, 1);

my $main_status = `systemctl is-active cloudflared 2>&1`;
chomp($main_status);
my $main_class = $main_status eq "active" ? "ui_green" : "ui_red";
my $main_label = $main_status eq "active" ? "Active" : "Inactive";

my $version = "";
if ($main_status eq "active") {
    $version = `$cloudflared_bin --version 2>&1`;
    chomp($version);
}

print &ui_table_start("Cloudflared Overview", "width=75%");
print &ui_table_row("Cloudflared Binary",
    $cloudflared_bin .
    ($bin_exists ? " <span style='color:green;font-size:10px;'>(found)</span>"
                 : " <span style='color:red;font-size:10px;'>(not found - install cloudflared)</span>"));
print &ui_table_row("Main Service Status",
    "<span class='$main_class'><b>$main_label</b></span>");
print &ui_table_row("Version", $version) if $version;
print &ui_table_end();

my @main_actions = (
    [ "start_service", "Start Service" ],
    [ "stop_service", "Stop Service" ],
    [ "restart_service", "Restart Service" ],
);

print &ui_hr();
print &ui_form_start("index.cgi", "get");
print &ui_table_start("Main Service Actions", "width=75%");
print &ui_table_row("Action",
    &ui_select("action", "", \@main_actions) . " " .
    &ui_submit("Execute"));
print &ui_table_end();
print &ui_form_end();

print &ui_hr();
print &ui_heading("Tunnels");

my @all_tunnels;
my %seen;

if ($tunnels_api && @$tunnels_api) {
    for my $t (@$tunnels_api) {
        $seen{$t->{name}} = 1;
        push @all_tunnels, $t;
    }
}

for my $t (@$tunnels_sys) {
    next if $seen{$t->{raw_name}};
    $seen{$t->{raw_name}} = 1;
    push @all_tunnels, $t;
}

for my $t (@$tunnels_cfg) {
    next if $seen{$t->{raw_name}};
    $seen{$t->{raw_name}} = 1;
    push @all_tunnels, $t;
}

if (@all_tunnels) {
    for my $t (@all_tunnels) {
        if ($t->{source} ne "systemd") {
            my $st = `systemctl is-active cloudflared-tunnel-$t->{raw_name} 2>&1`;
            chomp($st);
            $t->{status} = $st if $st =~ /^(active|inactive|failed)$/;
        }
    }

    print &ui_table_start("Configured Tunnels", "width=95%");

    my @headers = ("Tunnel Name", "Status", "Source", "Actions");
    &ui_columns_start(\@headers, ["30%", "15%", "15%", "40%"]);

    for my $t (@all_tunnels) {
        my $status_class = $t->{status} eq "active" ? "ui_green" : ($t->{status} eq "inactive" ? "ui_red" : "");
        my $status_label = $t->{status} || "unknown";

        my $actions;
        if ($t->{status} eq "active") {
            $actions = &ui_link("index.cgi?action=stop_tunnel&tunnel=$t->{raw_name}", "Stop") . " | ";
            $actions .= &ui_link("index.cgi?action=restart_tunnel&tunnel=$t->{raw_name}", "Restart");
        } else {
            $actions = &ui_link("index.cgi?action=start_tunnel&tunnel=$t->{raw_name}", "Start");
        }
        $actions .= " | ";
        $actions .= &ui_link("config.cgi?tunnel=$t->{raw_name}", "Config");
        $actions .= " | ";
        $actions .= &ui_link("logs.cgi?service=cloudflared-tunnel-$t->{raw_name}", "Logs");
        $actions .= " | ";
        $actions .= &ui_link("index.cgi?action=delete_tunnel&tunnel=$t->{raw_name}", "Delete");

        &ui_columns_row([
            $t->{name},
            "<span class='$status_class'><b>$status_label</b></span>",
            $t->{source} || "auto",
            $actions,
        ]);
    }

    &ui_columns_end();
    print &ui_table_end();
} else {
    print &ui_hr();
    show_message("error", "No tunnels found. Configure one in Settings or via cloudflared CLI.");
}

print &ui_hr();
print &ui_table_start("Management", "width=50%");
print &ui_table_row("Quick Links",
    &ui_link("config.cgi", "Settings & Config Editor") . " &nbsp; " .
    &ui_link("logs.cgi", "View Logs"));
print &ui_table_end();

&ui_print_footer("/", "Back to Webmin");
