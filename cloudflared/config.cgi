#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
our (%config, %in, %gconfig);
init_config();
ReadParse();

my $config_file = $config{'config_file'} || "";
my $cloudflared_bin = $config{'cloudflared'} || "";

my @config_paths = (
    "/etc/cloudflared/config.yml",
    "/etc/cloudflared/config.yaml",
    "$ENV{HOME}/.cloudflared/config.yml",
    "/root/.cloudflared/config.yml",
);

my @bin_paths = (
    "/usr/local/bin/cloudflared",
    "/usr/bin/cloudflared",
);

sub find_file {
    for my $p (@_) { return $p if -f $p; }
    return undef;
}

sub find_binary {
    for my $p (@_) { return $p if -x $p; }
    my $w = `which cloudflared 2>&1`;
    chomp($w);
    return $w if $w && -x $w;
    return undef;
}

if (!$config_file) { $config_file = find_file(@config_paths) || $config_paths[0]; }
if (!$cloudflared_bin) { $cloudflared_bin = find_binary(@bin_paths) || "/usr/local/bin/cloudflared"; }

my $detected_config = find_file(@config_paths);
my $detected_bin = find_binary(@bin_paths);
my $bin_exists = -x $cloudflared_bin;

my $action = $in{'action'} || '';
my $tunnel = $in{'tunnel'} || '';

sub show_message {
    my ($type, $text) = @_;
    my $color = $type eq "success" ? "#d4edda" : "#f8d7da";
    my $text_color = $type eq "success" ? "#155724" : "#721c24";
    my $border = $type eq "success" ? "#c3e6cb" : "#f5c6cb";
    print "<div style='margin:15px 0; padding:10px; background:$color; color:$text_color; border:1px solid $border; border-radius:4px;'>";
    print $text;
    print "</div>";
}

&ui_print_header(undef, "Cloudflared Settings", "", undef, 1);

if ($in{'save_settings'}) {
    &open_lock_config();
    $config{'config_file'} = $in{'config_file'} || "";
    $config{'cloudflared'} = $in{'cloudflared'} || "";
    &save_config();
    show_message("success", "Settings saved.");
    print &redirect("config.cgi");
    exit;
}

# --- Create tunnel ---
if ($action eq "create" && $in{'tunnel_name'}) {
    my $name = $in{'tunnel_name'};
    $name =~ s/[^a-zA-Z0-9_-]//g;
    if ($name) {
        my $r = `$cloudflared_bin tunnel create $name 2>&1`;
        if ($?) {
            show_message("error", "Failed to create tunnel: $r");
        } else {
            show_message("success", "Tunnel '$name' created successfully.");
            my $cred_file = "";
            if ($r =~ /credentials file at\s+(.+)$/m) { $cred_file = $1; }
            if ($r =~ /Written credentials file to\s+(.+)$/m) { $cred_file = $1; }
            if ($cred_file) {
                $cred_file =~ s/\s+$//;
                my $conf_dir = "/etc/cloudflared";
                my $conf_path = "$conf_dir/$name.yml";
                unless (-f $conf_path) {
                    open(my $fh, '>', $conf_path);
                    print $fh "# Tunnel: $name\n";
                    print $fh "tunnel: $name\n";
                    print $fh "credentials-file: $cred_file\n\n";
                    print $fh "ingress:\n";
                    print $fh "  - service: http://localhost:80\n";
                    close($fh);
                    show_message("success", "Auto-created config: $conf_path");
                }
                my $svc = "[Unit]\nDescription=Cloudflared Tunnel $name\nAfter=network.target\n\n[Service]\nType=simple\nExecStart=$cloudflared_bin tunnel run $name\nRestart=on-failure\nRestartSec=5\n\n[Install]\nWantedBy=multi-user.target\n";
                my $svc_path = "/etc/systemd/system/cloudflared-tunnel-$name.service";
                unless (-f $svc_path) {
                    open(my $fh, '>', $svc_path);
                    print $fh $svc;
                    close($fh);
                    `systemctl daemon-reload 2>&1`;
                    show_message("success", "Auto-created systemd service: cloudflared-tunnel-$name");
                }
            }
        }
    } else {
        show_message("error", "Invalid tunnel name. Use only letters, numbers, hyphens and underscores.");
    }
    print &ui_hr();
}

# --- Delete tunnel ---
if ($action eq "delete" && $tunnel) {
    my $t = $tunnel;
    $t =~ s/[^a-zA-Z0-9_-]//g;
    if ($t && $in{'confirm'} eq "yes") {
        my $r = `$cloudflared_bin tunnel delete $t 2>&1`;
        show_message($? == 0 ? "success" : "error", $? == 0 ? "Tunnel '$t' deleted." : $r);
        if (-f "/etc/cloudflared/$t.yml") { unlink("/etc/cloudflared/$t.yml"); }
        if (-f "/etc/systemd/system/cloudflared-tunnel-$t.service") { unlink("/etc/systemd/system/cloudflared-tunnel-$t.service"); }
        `systemctl daemon-reload 2>&1`;
    } else {
        &ui_print_header(undef, "Confirm Delete", "", undef, 1);
        &ui_confirm("Are you sure you want to delete tunnel '<b>$t</b>'? This will delete its config and systemd service.",
                     "config.cgi?action=delete&tunnel=$t&confirm=yes", "config.cgi",
                     "Yes, Delete", "Cancel");
        &ui_print_footer("index.cgi", "Back");
        exit;
    }
    print &ui_hr();
}

print &ui_form_start("config.cgi", "post");
print &ui_table_start("Module Settings", "width=80%");

print &ui_table_row("Cloudflared Binary",
    &ui_textbox("cloudflared", $cloudflared_bin, 50) .
    ($detected_bin ? " <span style='color:green;font-size:10px;'>(detected: $detected_bin)</span>"
                   : " <span style='color:red;font-size:10px;'>(not detected)</span>"));

print &ui_table_row("Default Config File",
    &ui_textbox("config_file", $config_file, 50) .
    ($detected_config ? " <span style='color:green;font-size:10px;'>(detected: $detected_config)</span>"
                      : " <span style='color:orange;font-size:10px;'>(not detected)</span>"));

print &ui_table_end();
print &ui_form_end([ [ "save_settings", "Save Settings" ] ]);

# --- Create news tunnel ---
print &ui_hr();
print &ui_heading("Create New Tunnel");

if ($bin_exists) {
    print &ui_form_start("config.cgi", "get");
    print &ui_table_start("Create Tunnel", "width=60%");
    print &ui_table_row("Tunnel Name",
        &ui_textbox("tunnel_name", "", 30) . " <i>(letters, numbers, hyphens, underscores)</i>");
    print &ui_table_end();
    print &ui_form_end([ [ "action=create", "Create Tunnel" ] ]);
} else {
    show_message("error", "Cloudflared binary not found. Cannot create tunnels.");
}

# --- Existing config files ---
print &ui_hr();
print &ui_heading("Configured Tunnels");

my $conf_dir = "/etc/cloudflared";
my @config_files;
if (-d $conf_dir) {
    opendir(my $dh, $conf_dir);
    while (my $f = readdir($dh)) {
        next if $f !~ /\.ya?ml$/;
        push @config_files, { name => $f, path => "$conf_dir/$f" };
    }
    closedir($dh);
    @config_files = sort { $a->{name} cmp $b->{name} } @config_files;
}

if (@config_files) {
    print &ui_table_start("Config Files", "width=95%");
    my @headers = ("File", "Path", "Actions");
    &ui_columns_start(\@headers, ["20%", "50%", "30%"]);

    for my $cf (@config_files) {
        my $tunnel_name = $cf->{name};
        $tunnel_name =~ s/\.ya?ml$//;
        my $actions = &ui_link("config.cgi?edit=$tunnel_name", "Edit") . " | " .
                      &ui_link("index.cgi?action=start_tunnel&tunnel=$tunnel_name", "Start") . " | " .
                      &ui_link("config.cgi?action=delete&tunnel=$tunnel_name", "Delete");
        &ui_columns_row([ $tunnel_name, $cf->{path}, $actions ]);
    }

    &ui_columns_end();
    print &ui_table_end();
} else {
    show_message("error", "No config files found in $conf_dir.");
}

# --- Per-tunnel config editor ---
my $edit_tunnel = $in{'edit'} || $tunnel;
if ($edit_tunnel) {
    $edit_tunnel =~ s/[^a-zA-Z0-9_-]//g;
    my $edit_path = "$conf_dir/$edit_tunnel.yml";
    $edit_path = "$conf_dir/$edit_tunnel.yaml" if !-f $edit_path;

    print &ui_hr();
    print &ui_heading("Editing Config: $edit_tunnel");

    if ($in{'save'}) {
        if (open(my $fh, '>', $edit_path)) {
            print $fh $in{'content'};
            close($fh);
            show_message("success", "Saved $edit_path");
        } else {
            show_message("error", "Failed to write $edit_path: $!");
        }
        print &ui_hr();
    }

    if (-f $edit_path) {
        my $content = "";
        if (open(my $fh, '<', $edit_path)) {
            local $/;
            $content = <$fh>;
            close($fh);
        }

        print &ui_form_start("config.cgi", "post");
        print &ui_table_start("Editing: $edit_path", "width=95%");
        print &ui_table_row("",
            &ui_textarea("content", $content, 30, 100) .
            &ui_hidden("edit", $edit_tunnel));
        print &ui_table_end();
        print &ui_form_end([ [ "save", "Save Config" ] ]);
        print &ui_link("index.cgi?action=start_tunnel&tunnel=$edit_tunnel", "Start this Tunnel") . " | ";
        print &ui_link("logs.cgi?service=cloudflared-tunnel-$edit_tunnel", "View Logs");
    } else {
        show_message("error", "File not found. Create it by creating the tunnel first.");
    }
} elsif (-f $config_file && $config_file !~ /^\Q$conf_dir\E/) {
    print &ui_hr();
    print &ui_heading("Default Config File");

    if ($in{'save'}) {
        if (open(my $fh, '>', $config_file)) {
            print $fh $in{'content'};
            close($fh);
            show_message("success", "Saved $config_file");
        } else {
            show_message("error", "Failed to write $config_file: $!");
        }
        print &ui_hr();
    }

    my $content = "";
    if (open(my $fh, '<', $config_file)) {
        local $/;
        $content = <$fh>;
        close($fh);
    } else {
        $content = "# Cloudflared configuration\n# See https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/config/\n\ntunnel: my-tunnel\ncredentials-file: /etc/cloudflared/credentials.json\n\n";
    }

    print &ui_form_start("config.cgi", "post");
    print &ui_table_start("Editing: $config_file", "width=95%");
    print &ui_table_row("",
        &ui_textarea("content", $content, 30, 100));
    print &ui_table_end();
    print &ui_form_end([ [ "save", "Save Config" ] ]);
}

&ui_print_footer("index.cgi", "Back to Manager");
