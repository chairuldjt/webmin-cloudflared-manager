#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
init_config();
ReadParse();

my $cloudflared_bin = $config{'cloudflared'} || "";

# --- Auto-detection ---
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

# --- Tunnel data ---
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
        my $load = $parts[1];
        my $active = $parts[2];
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
            active => $active,
            sub => $sub,
            source => "systemd",
            is_tunnel => $is_tunnel,
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
            path => $full,
        };
    }
    closedir($dh);
    return \@configs;
}

# --- Action handling ---
my $action = $in{'action'} || '';
my $confirm = $in{'confirm'} || '';
my $tunnel_name = $in{'tunnel'} || '';

if ($action && $confirm eq "yes") {
    &ui_print_header(undef, "Operation Result", "", undef, 1);

    if ($action eq "start_service") {
        my $r = `systemctl start cloudflared 2>&1`;
        &ui_print_result_message($? == 0, "Cloudflared service started.");
        &ui_print_result_message(0, $r) if $?;
    } elsif ($action eq "stop_service") {
        my $r = `systemctl stop cloudflared 2>&1`;
        &ui_print_result_message($? == 0, "Cloudflared service stopped.");
        &ui_print_result_message(0, $r) if $?;
    } elsif ($action eq "restart_service") {
        my $r = `systemctl restart cloudflared 2>&1`;
        &ui_print_result_message($? == 0, "Cloudflared service restarted.");
        &ui_print_result_message(0, $r) if $?;
    } elsif ($action eq "start_tunnel" && $tunnel_name) {
        my $r = `systemctl start cloudflared-tunnel-$tunnel_name 2>&1`;
        if ($?) {
            $r = `$cloudflared_bin tunnel run $tunnel_name --no-autoupdate 2>&1 &`;
            &ui_print_result_message(0, "No systemd service found. Tunnel started in background.");
        } else {
            &ui_print_result_message(1, "Tunnel '$tunnel_name' started.");
            &ui_print_result_message(0, $r) if $?;
        }
    } elsif ($action eq "stop_tunnel" && $tunnel_name) {
        my $r = `systemctl stop cloudflared-tunnel-$tunnel_name 2>&1`;
        if ($?) {
            $r = `pkill -f "cloudflared tunnel run $tunnel_name" 2>&1`;
            &ui_print_result_message($? == 0, "Tunnel '$tunnel_name' stopped.");
        } else {
            &ui_print_result_message(1, "Tunnel '$tunnel_name' stopped.");
        }
    } elsif ($action eq "restart_tunnel" && $tunnel_name) {
        my $r = `systemctl restart cloudflared-tunnel-$tunnel_name 2>&1`;
        &ui_print_result_message($? == 0, "Tunnel '$tunnel_name' restarted.");
        &ui_print_result_message(0, $r) if $?;
    } elsif ($action eq "delete_tunnel" && $tunnel_name) {
        my $r = `$cloudflared_bin tunnel delete $tunnel_name 2>&1`;
        &ui_print_result_message($? == 0, "Tunnel '$tunnel_name' deleted.");
        &ui_print_result_message(0, $r) if $?;
    }

    print &ui_hr();
    print &ui_link("index.cgi", "Back to Dashboard");
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

# --- Get tunnel data ---
my $tunnels_api = $bin_exists ? get_tunnels_from_list() : undef;
my $tunnels_sys = $bin_exists ? get_tunnels_from_systemd() : [];
my $tunnels_cfg = get_tunnels_from_configs();

# --- Render ---
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

# --- Main service info ---
my @info_rows;
push @info_rows, [ "Cloudflared Binary",
    $cloudflared_bin .
    ($bin_exists ? " <span style='color:green;font-size:10px;'>(found)</span>"
                 : " <span style='color:red;font-size:10px;'>(not found - install cloudflared)</span>") ];
push @info_rows, [ "Main Service Status",
    "<span class='$main_class'><b>$main_label</b></span>" ];
push @info_rows, [ "Version", $version ] if $version;

print &ui_info_table(\@info_rows, { title => "Cloudflared Overview", width => "75%" });

# --- Main service actions ---
print &ui_hr();
print &ui_form_start("index.cgi", "get");
print &ui_table_start({ title => "Main Service Actions", width => "75%" });
my @main_actions = (
    [ "start_service", "Start Service" ],
    [ "stop_service", "Stop Service" ],
    [ "restart_service", "Restart Service" ],
);
print &ui_table_row("Action",
    &ui_radio_select("action", "", \@main_actions) . " " .
    &ui_submit("Execute")
);
print &ui_table_end();
print &ui_form_end();

# --- Tunnels section ---
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
    # Merge tunnel info: check systemd status for each
    for my $t (@all_tunnels) {
        if ($t->{source} ne "systemd") {
            my $st = `systemctl is-active cloudflared-tunnel-$t->{raw_name} 2>&1`;
            chomp($st);
            $t->{status} = $st if $st =~ /^(active|inactive|failed)$/;
        }
    }

    print &ui_table_start({ title => "Configured Tunnels", width => "95%" });

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
    print &ui_notify_failure("No tunnels found. Configure one in Settings or via cloudflared CLI.");
}

# --- Create tunnel button ---
print &ui_hr();
print &ui_form_start("config.cgi", "get");
print &ui_table_start({ title => "Quick Actions", width => "50%" });
print &ui_table_row("Tunnel Management",
    &ui_link("config.cgi", "Settings & Config Editor") . " &nbsp; " .
    &ui_link("logs.cgi", "View Logs")
);
print &ui_table_end();
print &ui_form_end();

&ui_print_footer("/", "Back to Webmin");
